import contextvars, json, logging, sys, time, uuid

turn_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("turn_id", default=None)

def new_turn_id() -> str:
    tid = uuid.uuid4().hex[:12]
    turn_id_var.set(tid)
    return tid

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "msg": record.getMessage(),
            "turn_id": turn_id_var.get(),
        }
        payload.update(getattr(record, "data", {}) or {})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(path: str | None = None, level: int = logging.INFO) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if path:
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=handlers, force=True)