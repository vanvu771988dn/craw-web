from dataclasses import dataclass


@dataclass(slots=True)
class BatchProcessingStats:
    discovered: int = 0
    processed: int = 0
    saved: int = 0
    duplicates: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass(slots=True)
class RunStats:
    batches: int = 0
    discovered: int = 0
    processed: int = 0
    saved: int = 0
    duplicates: int = 0
    failed: int = 0
    skipped: int = 0

    def add_batch(self, batch: BatchProcessingStats) -> None:
        self.batches += 1
        self.discovered += batch.discovered
        self.processed += batch.processed
        self.saved += batch.saved
        self.duplicates += batch.duplicates
        self.failed += batch.failed
        self.skipped += batch.skipped
