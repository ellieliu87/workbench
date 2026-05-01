"""Data Services router — drives the Data tab's "Data Services" section.

Returns three groups of cards (Predictive Analytics built-ins, CCAR
scenarios per year, internal Outlook scenarios) plus integration-status
badges so the frontend can show whether each group is backed by a live
corporate integration (`pa_common_tools` package, OneLake table) or by
the static fallback specs in `services/data_services.py`.

The single endpoint covers the whole section so the frontend does one
fetch and renders. Year filtering is client-side because the payload is
small enough; pass `?year=YYYY` to restrict the CCAR portion server-side
when OneLake reads get heavy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from models.schemas import (
    DataServiceCard,
    DataServicesIntegrationStatus,
    DataServicesPayload,
)
from routers.auth import get_current_user
from services import data_services as ds

router = APIRouter()


def _to_card(c: ds.ServiceCard) -> DataServiceCard:
    return DataServiceCard(**c.to_dict())


def _to_status(s: ds.IntegrationStatus) -> DataServicesIntegrationStatus:
    return DataServicesIntegrationStatus(**s.to_dict())


@router.get("", response_model=DataServicesPayload)
async def get_data_services(
    function_id: str = Query(..., description="Function id this section belongs to"),
    year: str | None = Query(default=None, description="Restrict CCAR to a single year"),
    _: str = Depends(get_current_user),
):
    predictive_cards, pa_status = ds.list_predictive_cards()
    ccar_years, ccar_by_year, ccar_status = ds.list_ccar(year_filter=year)
    outlook_cards, outlook_status = ds.list_outlook()

    return DataServicesPayload(
        function_id=function_id,
        predictive=[_to_card(c) for c in predictive_cards],
        predictive_status=_to_status(pa_status),
        ccar_years=ccar_years,
        ccar_scenarios={y: [_to_card(c) for c in cards] for y, cards in ccar_by_year.items()},
        ccar_status=_to_status(ccar_status),
        outlook=[_to_card(c) for c in outlook_cards],
        outlook_status=_to_status(outlook_status),
    )
