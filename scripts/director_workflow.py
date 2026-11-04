#!/usr/bin/env python3
"""Local CLI for the review-gated workflow; defaults to a simulated provider."""

import argparse
import json
import sys
from pathlib import Path

from hc_workflow.engine import Engine, WorkflowError


def read_json(path):
    with Path(path).expanduser().open(encoding="utf-8") as stream:
        return json.load(stream)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(Path.home() / ".local/state/hardcore-director/workflows.sqlite3"), help="private local SQLite database outside the Skill directory")
    p.add_argument("--config", help="explicit provider configuration JSON; no auto-discovery")
    p.add_argument("--artifacts", help="directory for this workflow's output files")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a project; no provider writes")
    init.add_argument("--brief", default="")
    init.add_argument("--brief-file")
    init.add_argument("--project-id")
    init.add_argument("--mode", choices=("dry-run", "mock", "live"), default="dry-run")
    init.add_argument("--actor", default="local")
    plan = sub.add_parser("plan", aliases=["draft"], help="save a shot plan, or explicitly request a model draft")
    plan.add_argument("project_id")
    source = plan.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="an existing shot-plan JSON")
    source.add_argument("--brief-file", help="a UTF-8 brief; no model call without the explicit flag")
    plan.add_argument("--allow-model-usage", action="store_true")
    plan.add_argument("--model")
    plan.add_argument("--references", help="JSON array of explicitly provided reference assets")
    plan.add_argument("--image-provider", default="mock")
    plan.add_argument("--video-provider", default="mock")
    plan.add_argument("--actor", default="local")
    status = sub.add_parser("status")
    status.add_argument("project_id")
    approve = sub.add_parser("approve", help="record a human decision; live budget/scope are separate")
    approve.add_argument("project_id")
    approve.add_argument("--stage", choices=("plan", "storyboard", "composition", "final"), required=True)
    approve.add_argument("--actor", required=True)
    approve.add_argument("--shot", action="append", dest="shot_ids")
    approve.add_argument("--revision", type=int)
    approve.add_argument("--binding-hash")
    approve.add_argument("--ttl", type=int, default=3600)
    approve.add_argument("--budget", help="stage cumulative ceiling, as a Decimal string")
    approve.add_argument("--currency", default="CNY")
    approve.add_argument("--live-stage", choices=("image", "video"), action="append", default=[])
    approve.add_argument("--provider", help="exact provider identity being authorized")
    approve.add_argument("--account", help="exact verified account identity being authorized")
    approve.add_argument("--allow-uploads", action="store_true")
    reject = sub.add_parser("reject", help="reject specific images/videos; require fresh approvals")
    reject.add_argument("project_id")
    reject.add_argument("--stage", choices=("plan", "storyboard", "composition", "final"), required=True)
    reject.add_argument("--actor", required=True)
    reject.add_argument("--shot", action="append", dest="shot_ids")
    reject.add_argument("--reason", default="")
    reject.add_argument("--revision", type=int)
    tick = sub.add_parser("tick", help="advance one provider action; never auto-approve")
    tick.add_argument("project_id")
    tick.add_argument("--steps", type=int, default=1, help="1..100; live projects permit only 1")
    resume = sub.add_parser("resume", help="local evidence-based recovery; uncertain mutations stay poll-only")
    resume.add_argument("project_id")
    resume.add_argument("--operation", required=True)
    resume.add_argument("--actor", required=True)
    sub.add_parser("doctor", help="read-only provider readiness; no account/login/setup changes")
    return p


def build_engine(args):
    from hc_workflow.providers import get_provider
    config = read_json(args.config) if args.config else {}
    providers = {"mock": get_provider("mock")}
    for name, settings in config.get("providers", {}).items():
        providers[name] = get_provider(name, settings)
    return Engine(args.db, providers=providers, artifact_dir=args.artifacts)


def main(argv=None):
    args = parser().parse_args(argv)
    engine = None
    try:
        engine = build_engine(args)
        if args.command == "init":
            brief = Path(args.brief_file).expanduser().read_text(encoding="utf-8") if args.brief_file else args.brief
            result = engine.init_project(brief, actor=args.actor, mode=args.mode, project_id=args.project_id)
        elif args.command in ("plan", "draft"):
            if args.file:
                result = engine.set_plan(args.project_id, read_json(args.file), actor=args.actor)
            else:
                from hc_workflow.planner import generate_plan, to_engine_plan
                references = read_json(args.references) if args.references else []
                proposal = generate_plan(Path(args.brief_file).expanduser().read_text(encoding="utf-8"),
                                         references=references, model=args.model,
                                         allow_model_usage=args.allow_model_usage)
                if proposal.get("status") == "succeeded":
                    value = to_engine_plan(proposal["creative_plan"], references=references,
                                           image_provider=args.image_provider, video_provider=args.video_provider)
                    result = engine.set_plan(args.project_id, value, actor=args.actor)
                else:
                    result = proposal
        elif args.command == "status":
            result = engine.status(args.project_id)
        elif args.command == "approve":
            scope = None
            if args.live_stage:
                current = engine.status(args.project_id)
                binding = current["bindings"].get(args.stage)
                if not binding:
                    raise WorkflowError("this stage is not ready for review")
                if not args.provider or not args.account or args.budget is None:
                    raise WorkflowError("live approval requires --provider, --account and --budget")
                scope = {"stages": args.live_stage, "provider": args.provider, "account": args.account,
                         "allow_uploads": args.allow_uploads, "revision": binding["revision"],
                         "plan_hash": binding["plan_hash"], "asset_hash": binding["asset_hash"]}
            result = engine.approve(args.project_id, stage=args.stage, actor=args.actor,
                                    shot_ids=args.shot_ids, ttl_seconds=args.ttl,
                                    budget={"amount": args.budget, "currency": args.currency} if args.budget is not None else None,
                                    live_scope=scope, expected_revision=args.revision,
                                    expected_binding_hash=args.binding_hash)
        elif args.command == "reject":
            result = engine.reject(args.project_id, stage=args.stage, actor=args.actor,
                                   shot_ids=args.shot_ids, reason=args.reason, expected_revision=args.revision)
        elif args.command == "tick":
            if not 1 <= args.steps <= 100:
                raise WorkflowError("tick --steps must be between 1 and 100")
            if args.steps > 1 and engine.status(args.project_id)["mode"] == "live":
                raise WorkflowError("live tick advances one action only; use an authorized scheduler")
            for _ in range(args.steps):
                result = engine.tick(args.project_id)
                if result.get("blocked_reason") or result["status"] in ("plan_review", "storyboard_review", "composition_review", "composition_rejected", "final_review", "completed", "brief"):
                    break
        elif args.command == "resume":
            result = engine.resume(args.project_id, args.operation, actor=args.actor)
        else:
            result = engine.doctor()
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (WorkflowError, ValueError, OSError, KeyError, ImportError) as exc:
        print(json.dumps({"status": "refused", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if engine:
            engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
