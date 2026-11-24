import asyncio
from unittest.mock import AsyncMock

import pytest

from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
from application.services.equipment_service import (
    EquipmentImageAlreadyExistsError,
    EquipmentImageGenerationInProgressError,
    EquipmentImageGenerationUnavailableError,
    EquipmentService,
)
from domain.models.equipment import Equipment
from domain.models.generated_image import GeneratedImage
from domain.ports.output.image_generator import ImageGenerator


def _generated_image() -> GeneratedImage:
    return GeneratedImage.model_validate({
        "image": {
            "bucket": "equipment",
            "key": "equipment/fouet/main/image.png",
            "url": "/api/media/v1/buckets/equipment/objects/equipment/fouet/main/image.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "test",
    })


async def test_generate_main_image_requires_configured_generator(logger):
    service = EquipmentService(InMemoryEquipmentRepository(), logger)
    equipment = await service.create(Equipment(name="Fouet"))

    with pytest.raises(EquipmentImageGenerationUnavailableError):
        await service.generate_main_image(equipment.uuid)


async def test_generate_main_image_builds_equipment_brief_and_persists_url(logger):
    generator = AsyncMock(spec=ImageGenerator)
    generator.generate.return_value = _generated_image()
    service = EquipmentService(
        InMemoryEquipmentRepository(),
        logger,
        image_generator=generator,
    )
    equipment = await service.create(Equipment(name="Fouet", description="Fouet ballon en inox"))

    updated, generated = await service.generate_main_image(equipment.uuid)

    assert updated.main_image == generated.image.url
    call = generator.generate.await_args.kwargs
    assert call["bucket"] == "equipment"
    assert call["object_prefix"] == f"equipment/{equipment.uuid}/main"
    assert "Fouet" in call["brief"]
    assert "Fouet ballon en inox" in call["brief"]


async def test_generate_main_image_refuses_implicit_replacement(logger):
    generator = AsyncMock(spec=ImageGenerator)
    service = EquipmentService(
        InMemoryEquipmentRepository(),
        logger,
        image_generator=generator,
    )
    equipment = await service.create(Equipment(name="Fouet", main_image="/existing.png"))

    with pytest.raises(EquipmentImageAlreadyExistsError):
        await service.generate_main_image(equipment.uuid)

    generator.generate.assert_not_awaited()


async def test_generate_main_image_reserves_equipment_against_duplicate_requests(logger):
    started = asyncio.Event()
    finish = asyncio.Event()

    async def generate_once(**_kwargs):
        started.set()
        await finish.wait()
        return _generated_image()

    generator = AsyncMock(spec=ImageGenerator)
    generator.generate.side_effect = generate_once
    service = EquipmentService(
        InMemoryEquipmentRepository(),
        logger,
        image_generator=generator,
    )
    equipment = await service.create(Equipment(name="Fouet"))

    first = asyncio.create_task(service.generate_main_image(equipment.uuid))
    await started.wait()
    with pytest.raises(EquipmentImageGenerationInProgressError):
        await service.generate_main_image(equipment.uuid)
    finish.set()
    await first

    assert generator.generate.await_count == 1
