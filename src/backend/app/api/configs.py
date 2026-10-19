from fastapi import APIRouter, HTTPException, Response

from app.configs import store
from app.schemas.config import (
    ConfigListResponse,
    ConfigSummary,
    ConfigUpload,
    SavedConfig,
)

router = APIRouter(prefix="/api/configs", tags=["configs"])


@router.get("", response_model=ConfigListResponse)
def list_configs() -> ConfigListResponse:
    return ConfigListResponse(
        configs=[ConfigSummary.of(config) for config in store.list_configs()]
    )


@router.get("/{config_id}", response_model=SavedConfig)
def get_config(config_id: str) -> SavedConfig:
    try:
        return store.get_config(config_id)
    except store.ConfigNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("", response_model=SavedConfig, status_code=201)
def upload_config(upload: ConfigUpload) -> SavedConfig:
    try:
        return store.save_config(upload)
    except store.DuplicateConfigNameError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{config_id}", status_code=204, response_class=Response)
def delete_config(config_id: str) -> Response:
    try:
        store.delete_config(config_id)
    except store.BuiltinConfigError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except store.ConfigNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
