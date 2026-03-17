from pathlib import Path
from arclith import Arclith
from adapters.input.fastapi.router import Router
from infrastructure.container import build_service

arclith = Arclith(Path(__file__).parent / "config.yaml")
services = build_service(arclith)

app = arclith.fastapi()
app.include_router(Router(services.ingredient, services.recipe, services.tool, services.logger).router)

if __name__ == "__main__":
    arclith.run_api("main_api:app")
