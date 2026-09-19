from dataclasses import dataclass, field


@dataclass(slots=True)
class CrawlStageError(Exception):
    stage: str
    code: str
    message: str
    context: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        if not self.context:
            return f"[{self.stage}:{self.code}] {self.message}"
        return f"[{self.stage}:{self.code}] {self.message} | context={self.context}"
