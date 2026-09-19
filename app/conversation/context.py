from __future__ import annotations

from pydantic import BaseModel, Field


class ResolvedContext(BaseModel):
    geo_ids: list[str] = Field(default_factory=list)
    geo_names: list[str] = Field(default_factory=list)
    field_id: str | None = None
    field_name: str | None = None
    vintage: int | None = None

    def update_from_traces(self, traces: list) -> None:
        from app.agent.composer import ToolCallTrace

        for trace in traces:
            if not isinstance(trace, ToolCallTrace) or trace.result_kind != "success":
                continue
            if trace.data is None:
                continue
            if trace.name == "find_geography":
                self.geo_ids = [str(trace.data["geo_id"])]
                self.geo_names = [str(trace.data["name"])]
            elif trace.name == "get_value":
                self.field_id = str(trace.data["field_id"])
                self.field_name = str(trace.data["field_name"])
                self.geo_ids = [str(trace.data["geo_id"])]
                self.geo_names = [str(trace.data["geography_name"])]
                self.vintage = int(trace.data["vintage"])
            elif trace.name == "rank_geographies":
                self.field_id = str(trace.data["field_id"])
                self.vintage = int(trace.data["vintage"])
            elif trace.name == "compare":
                self.field_id = str(trace.data["field_id"])
                self.vintage = int(trace.data["vintage"])
                geographies = trace.data.get("geographies") or []
                self.geo_ids = [str(item["geo_id"]) for item in geographies]
                self.geo_names = [str(item["geography_name"]) for item in geographies]
            elif trace.name == "get_trend":
                self.field_id = str(trace.data["field_id"])
                self.geo_ids = [str(trace.data["geo_id"])]
            elif trace.name == "find_variable":
                candidates = trace.data.get("candidates") or []
                if candidates:
                    first = candidates[0]
                    self.field_id = str(first["field_id"])
                    self.field_name = str(first["name"])

    def as_facts(self) -> list[str]:
        facts: list[str] = []
        if self.field_name and self.field_id:
            facts.append(f"Variable: {self.field_name} ({self.field_id})")
        elif self.field_id:
            facts.append(f"Variable: {self.field_id}")
        if self.geo_names and self.geo_ids and len(self.geo_names) == len(self.geo_ids):
            if len(self.geo_names) == 1:
                facts.append(f"Geography: {self.geo_names[0]} ({self.geo_ids[0]})")
            else:
                pairs = ", ".join(
                    f"{name} ({geo_id})"
                    for name, geo_id in zip(self.geo_names, self.geo_ids, strict=True)
                )
                facts.append(f"Geographies: {pairs}")
        if self.vintage is not None:
            facts.append(f"Vintage: {self.vintage}")
        return facts
