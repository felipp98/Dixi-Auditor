"""
Utilitário para despacho de tarefas em segundo plano e comunicação thread-safe com Tkinter.
"""
import threading
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

def run_async_task(
    task_func: Callable[..., Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    on_finally: Optional[Callable[[], None]] = None,
    root_widget: Optional[Any] = None,
    args: tuple = (),
    kwargs: Optional[dict] = None
) -> threading.Thread:
    """
    Executa task_func em uma thread background (daemon) e encaminha os resultados
    ou exceções de forma segura para a thread principal do Tkinter via root_widget.after(0, ...).
    """
    if kwargs is None:
        kwargs = {}

    def worker():
        try:
            result = task_func(*args, **kwargs)
            if on_success:
                if root_widget and hasattr(root_widget, "after"):
                    root_widget.after(0, lambda: on_success(result))
                else:
                    on_success(result)
        except Exception as e:
            logger.exception(f"Exceção capturada em tarefa assíncrona: {e}")
            if on_error:
                if root_widget and hasattr(root_widget, "after"):
                    root_widget.after(0, lambda err=e: on_error(err))
                else:
                    on_error(e)
        finally:
            if on_finally:
                if root_widget and hasattr(root_widget, "after"):
                    root_widget.after(0, on_finally)
                else:
                    on_finally()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
