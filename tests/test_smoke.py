#!/usr/bin/env python3
"""Offline smoke tests for Ghost studio tools (no live board required)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))


class LengthProfileTests(unittest.TestCase):
    def test_profiles_load(self):
        import length_profiles as lp

        data = lp.load_length_profiles(ROOT)
        for key in ("short_story", "novelette", "novella", "novel"):
            self.assertIn(key, data["profiles"])
        self.assertEqual(lp.profile_for_key("short_story", ROOT)["scene_min_words"], 400)
        ss = lp.profile_for_key("short_story", ROOT)
        self.assertEqual(ss.get("target_reader_cadence"), "after_opening")
        self.assertEqual(ss.get("early_reader_after_scene"), 1)
        self.assertEqual(ss.get("target_word_min"), 4000)
        self.assertEqual(ss.get("target_word_max"), 5000)
        self.assertEqual(ss.get("typical_scenes_min"), 4)
        self.assertEqual(ss.get("typical_scenes_max"), 6)
        self.assertEqual(lp.profile_for_key("novella", ROOT)["scene_min_words"], 800)
        self.assertEqual(lp.infer_profile_from_target(5000, ROOT)["key"], "short_story")


class RolePackTests(unittest.TestCase):
    def test_draft_pack_slim(self):
        import role_packs as rp

        work, paths, spec = rp.pack_paths("drafting_author", "draft", "SCENE-003")
        self.assertEqual(work, "draft")
        self.assertLessEqual(len(paths), 8)
        card = rp.job_card(
            "drafting_author",
            "draft",
            "SCENE-003",
            "/ws",
            {"book_slug": "demo", "working_title": "Demo"},
            min_words=400,
        )
        self.assertEqual(card["primary_command"], "pack")
        self.assertTrue(str(card["deliverable_path"]).endswith("SCENE-003.md"))

    def test_me_and_sa_primary(self):
        import role_packs as rp

        me = rp.job_card("managing_editor", "stage_advance", None, "/ws", {"book_slug": "demo"})
        sa = rp.job_card("studio_administrator", "git_sync", None, "/ws", {"book_slug": "demo"})
        self.assertEqual(me["primary_command"], "watchdog")
        self.assertEqual(sa["primary_command"], "git-sync")


class CraftLintTests(unittest.TestCase):
    def test_rejects_verbatim_loop(self):
        import craft_lint

        mantra = "She had the facts. She had the dissent. She had the records. "
        text = (mantra * 40).strip() + "\n"
        result = craft_lint.lint_text(text, allow_draft_infer=True)
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("ok", True))


class ScrubTests(unittest.TestCase):
    BANNED = ("paperclip", "opencode", "mypuck", "cheapest/", "pcp_board")

    def test_repo_scrub(self):
        banned_hits = []
        skip = {".git", "__pycache__", ".venv"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(s in path.parts for s in skip):
                continue
            if "tests" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".py", ".yaml", ".yml", ".txt", ".example"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            for token in self.BANNED:
                if token in text:
                    banned_hits.append(f"{path.relative_to(ROOT)}:{token}")
        self.assertEqual(banned_hits, [], msg="\n".join(banned_hits[:20]))



class CraftAndEarlyReaderTests(unittest.TestCase):
    def test_craft_pack_excludes_self_eval(self):
        import role_packs as rp

        pack = rp.WORK_PACKS["craft_audit"]
        files = pack["files"]
        self.assertEqual(
            files,
            [
                "development/CREATIVE_BRIEF.md",
                "bible/STYLE_GUIDE.md",
                "outline/scenes/{unit}.md",
                "manuscript/scenes/{unit}.md",
            ],
        )
        never = pack.get("files_never") or []
        self.assertTrue(any("self_eval" in x for x in never))

    def test_craft_audit_pass_requires_evidence(self):
        import importlib.util
        import json
        from tempfile import TemporaryDirectory

        spec = importlib.util.spec_from_file_location("studio_mod", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "reviews").mkdir()
            unit = "SCENE-001"
            payload = {
                "unit": unit,
                "verdict": "PASS",
                "approved": True,
                "desire_to_continue": 4,
                "quotes": ["alpha quote here", "beta quote here"],
                "findings": [],
                "revision_directive": "",
                "summary": "ok",
            }
            (ws / "reviews" / f"{unit}_craft_audit.json").write_text(json.dumps(payload), encoding="utf-8")
            audit = mod.read_craft_audit(ws, unit)
            self.assertTrue(mod.craft_audit_is_pass(audit))
            payload["quotes"] = ["only one"]
            (ws / "reviews" / f"{unit}_craft_audit.json").write_text(json.dumps(payload), encoding="utf-8")
            audit = mod.read_craft_audit(ws, unit)
            self.assertFalse(mod.craft_audit_is_pass(audit))

    def test_early_reader_required_once(self):
        import importlib.util
        from tempfile import TemporaryDirectory

        spec = importlib.util.spec_from_file_location("studio_mod2", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "reviews").mkdir()
            book = {
                "workflow_profile": "short_story",
                "target_reader_cadence": "after_opening",
                "early_reader_after_scene": 1,
            }
            self.assertTrue(mod.early_reader_required(book, ws, "SCENE-001"))
            self.assertFalse(mod.early_reader_required(book, ws, "SCENE-002"))
            (ws / "reviews" / "EARLY_READER_CHECKPOINT.md").write_text("Verdict: continue\n", encoding="utf-8")
            self.assertFalse(mod.early_reader_required(book, ws, "SCENE-001"))
            self.assertIsNone(mod.early_reader_blocks_next_draft(ws, book))
            (ws / "reviews" / "EARLY_READER_CHECKPOINT.md").write_text(
                "Verdict: revise_opening\n", encoding="utf-8"
            )
            self.assertEqual(
                mod.early_reader_blocks_next_draft(ws, book),
                "EARLY_READER_CHECKPOINT.md:revise_opening",
            )

    def test_pilot_templates_exist(self):
        for name in (
            "EXPERIMENT_METRICS.md",
            "PILOT_POSTMORTEM.md",
            "CONTROLLED_TEST.md",
            "EARLY_READER_CHECKPOINT.md",
        ):
            self.assertTrue((ROOT / "studio/versions/0.1.0/templates" / name).is_file())
        self.assertTrue((ROOT / "studio/versions/0.1.0/schemas/craft_audit.schema.json").is_file())


class PackContractTests(unittest.TestCase):
    def test_job_card_has_write_contract(self):
        import role_packs as rp

        card = rp.job_card(
            "story_architect",
            "creative_brief",
            None,
            "/ws/_default",
            {"book_slug": "demo", "working_title": "Demo", "controlled_test": True},
        )
        self.assertEqual(card["write_root"], "/ws/_default")
        self.assertIn("done_gate", card)
        self.assertEqual(card["done_gate"]["require_path_prefix"], "/ws/_default")
        self.assertTrue(card["done_gate"]["reject_if_sections_empty"])
        self.assertFalse(card["board_policy"]["allow_board_approval"])
        self.assertTrue(any(p.get("rel") == "development/CREATIVE_BRIEF.md" for p in card["write_plan"]))

    def test_empty_required_sections(self):
        import role_packs as rp

        template = """# Creative Brief\n\n## One-sentence concept\n\n\n## Format and target length\n\n- Format: short_story\n"""
        empty = rp.empty_required_sections(
            template,
            ["One-sentence concept", "Format and target length", "Audience"],
        )
        self.assertIn("One-sentence concept", empty)
        self.assertNotIn("Format and target length", empty)
        self.assertIn("Audience", empty)


class ProjectsRootGuardTests(unittest.TestCase):
    def test_doubled_company_root_rejected(self):
        import importlib.util
        from tempfile import TemporaryDirectory

        spec = importlib.util.spec_from_file_location("studio_mod_root", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        # Avoid SystemExit from missing env during import side effects; module loads env optionally.
        spec.loader.exec_module(mod)
        with TemporaryDirectory() as td:
            root = Path(td) / "projects" / "company123"
            root.mkdir(parents=True)
            with self.assertRaises(SystemExit):
                mod.validate_projects_root(root, company_id="company123")


class VerifyDonePathTests(unittest.TestCase):
    def test_rejects_tmp_and_empty_brief_section(self):
        import importlib.util
        import json
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace

        spec = importlib.util.spec_from_file_location("studio_mod_vd", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with TemporaryDirectory() as td:
            ws = Path(td) / "_default"
            (ws / "development").mkdir(parents=True)
            brief = ws / "development" / "CREATIVE_BRIEF.md"
            brief.write_text(
                """---\nstatus: PROPOSED\n---\n\n# Creative Brief\n\n## One-sentence concept\n\n\n## Format and target length\n\nx\n\n## Audience\n\nx\n\n## Genre and story promise\n\nx\n\n## Tone and emotional experience\n\nx\n\n## POV and tense\n\nx\n\n## Required elements\n\nx\n\n## Forbidden elements\n\nx\n""",
                encoding="utf-8",
            )
            # empty One-sentence concept should fail
            args = SimpleNamespace(
                path=str(brief),
                min_words=1,
                not_identical_to=None,
                skip_craft_lint=True,
                write_root=str(ws),
            )
            with self.assertRaises(SystemExit) as ctx:
                mod.cmd_verify_done(args)
            self.assertEqual(ctx.exception.code, 1)
            # fill concept and pass
            brief.write_text(
                """---\nstatus: PROPOSED\n---\n\n# Creative Brief\n\n## One-sentence concept\n\nA real concept lives here.\n\n## Format and target length\n\nshort_story\n\n## Audience\n\nadults\n\n## Genre and story promise\n\nliterary\n\n## Tone and emotional experience\n\nrestrained\n\n## POV and tense\n\nthird past\n\n## Required elements\n\nobjects\n\n## Forbidden elements\n\nsubplots\n""",
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as ctx_ok:
                mod.cmd_verify_done(args)
            self.assertEqual(ctx_ok.exception.code, 0)
            self.assertEqual(mod.path_is_forbidden_deliverable(Path("/tmp/nope.md")), "tmp_not_allowed")
            self.assertEqual(
                mod.path_is_forbidden_deliverable(Path("/x/repos/AI/books/a.md")),
                "repos_checkout_not_allowed",
            )
            self.assertEqual(
                mod.path_is_forbidden_deliverable(
                    Path(str(ws) + "/development/CREATIVE_BRIEF.md"),
                    write_root=str(ws),
                ),
                None,
            )




class StartBookTests(unittest.TestCase):
    def test_start_book_plan_short_story(self):
        from start_book import build_start_plan, render_book_yaml
        plan = build_start_plan(
            title="The Last Box",
            prompt="prompt body",
            format_name="short_story",
            controlled_test=True,
            target_words=4500,
        )
        self.assertEqual(plan["slug"], "the-last-box")
        self.assertEqual(plan["profile_key"], "short_story")
        yaml_text = render_book_yaml(
            book_id="bid",
            title="The Last Box",
            slug="the-last-box",
            project_id="pid",
            profile=plan["profile"],
            controlled_test=True,
            target_words=4500,
        )
        self.assertIn("controlled_test: true", yaml_text)
        self.assertIn("early_reader_after_scene:", yaml_text)


class StageHandoffTests(unittest.TestCase):
    def test_studio_cli_prefers_absolute_when_present(self):
        import importlib.util
        import os
        from unittest import mock

        spec = importlib.util.spec_from_file_location("studio_mod_cli", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {"STUDIO_CLI": ""}, clear=False):
            # Ensure STUDIO_CLI empty for this check
            os.environ.pop("STUDIO_CLI", None)
            spec.loader.exec_module(mod)
            cli = mod.studio_cli()
        self.assertTrue(cli.startswith("python3 "), cli)
        self.assertIn("studio.py", cli)
        # Prefer absolute path over bare tools/studio.py when __file__ exists
        self.assertFalse(cli.endswith("tools/studio.py") and not cli.startswith("python3 /"), cli)

    def test_stage_handoff_map_includes_creative_brief(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("studio_mod_ho", str(ROOT / "tools" / "studio.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("creative_brief", mod.STAGE_HANDOFF_NEXT)
        self.assertEqual(mod.STAGE_HANDOFF_NEXT["creative_brief"][0], "premise")
        self.assertIn("ending", mod.STAGE_HANDOFF_NEXT)


if __name__ == "__main__":
    unittest.main()
