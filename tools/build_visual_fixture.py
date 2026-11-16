"""Build an explicitly labelled offline scene for browser QA; never calls a model provider."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from raiz_sar.contracts import PlanRequest
from raiz_sar.plans import build_plan
from raiz_sar.scenarios import get_scenario
from raiz_sar.scene import generate_scene, fixture_scene_responder
from raiz_sar.ai_provider import FixtureProvider


def main():
    scenario = get_scenario("lower-piura-sechura")
    plan = build_plan(PlanRequest(scenario_id=scenario["summary"]["scenario_id"], dataset_version=scenario["summary"]["dataset_version"], budget_pen=15000))
    scene = generate_scene(plan, scenario, FixtureProvider(fixture_scene_responder))
    dest = Path(".local/qa/performance/fixture.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"scenario": scenario, "plan": plan.model_dump(mode="json"), "scene": scene.model_dump(mode="json")}), encoding="utf-8")
    print("Explicit fixture scene created; no actual model inference.")


if __name__ == "__main__":
    main()
