"""What goes wrong when pylekto talks to Lekto, and the warning about another Lekto version."""

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from uuid import UUID

    from pylekto.models import InputErrorOut, Problem, ReasonOut


class LektoError(Exception):
    """Base of every error pylekto raises."""


class LektoConnectionError(LektoError):
    """Lekto could not be reached, the connection broke off, or its answer could not be read."""


class LektoTimeoutError(LektoConnectionError):
    """Lekto did not answer in time."""


class LektoResponseError(LektoError):
    """Lekto answered with something pylekto's models do not describe.

    Most likely Lekto speaks another version of its API than pylekto
    (:data:`pylekto.API_VERSION`).
    """


class LektoApiError(LektoError):
    """Lekto refused a request; :attr:`problem` holds its problem details (RFC 9457).

    Args:
        problem: The problem details of Lekto's answer.

    Example::

        try:
            me = await lekto.auth.me()
        except LektoApiError as error:
            print(error.status, error.reason.code if error.reason else error.problem.title)

    """

    def __init__(self, problem: Problem) -> None:
        """Hold the problem details; the message is the status, the title and the detail."""
        detail = f": {problem.detail}" if problem.detail else ""
        super().__init__(f"{problem.status} {problem.title}{detail}")
        self.problem = problem

    def __reduce__(self) -> tuple[type[Self], tuple[object, ...]]:
        """Copy and pickle from the problem details: ``args`` holds only the message."""
        return type(self), (self.problem,)

    @property
    def status(self) -> int:
        """The HTTP status of Lekto's answer."""
        return self.problem.status

    @property
    def reason(self) -> ReasonOut | None:
        """Why Lekto refused, as a code with parameters beside the English text."""
        return self.problem.reason

    @property
    def errors(self) -> list[InputErrorOut]:
        """What was wrong with each part of the request (with 422)."""
        return self.problem.errors or []


class LektoAuthenticationError(LektoApiError):
    """401: the token is missing, unknown, expired or revoked."""


class LektoForbiddenError(LektoApiError):
    """403: the token's rights or the user's role do not allow the request."""


class LektoNotFoundError(LektoApiError):
    """404: the object does not exist, or the caller may not see it."""


class LektoConflictError(LektoApiError):
    """409: the request collides with what Lekto holds, such as a file it holds already."""

    @property
    def existing_document_id(self) -> UUID | None:
        """The document an uploaded file collided with, if the caller may read it."""
        return self.problem.existing_document_id


class LektoValidationError(LektoApiError):
    """422: Lekto refused values of the request; :attr:`errors` names each one."""


class LektoRateLimitError(LektoApiError):
    """429: too many requests.

    Args:
        problem: The problem details of Lekto's answer.
        retry_after: Seconds to wait, if Lekto said so (``Retry-After``).

    Example::

        try:
            await lekto.auth.me()
        except LektoRateLimitError as error:
            await asyncio.sleep(error.retry_after or 5)

    """

    def __init__(self, problem: Problem, retry_after: float | None) -> None:
        """Hold the problem details and the seconds to wait."""
        super().__init__(problem)
        self.retry_after = retry_after

    def __reduce__(self) -> tuple[type[Self], tuple[object, ...]]:
        """Copy and pickle with the seconds to wait as well."""
        return type(self), (self.problem, self.retry_after)


class LektoServerError(LektoApiError):
    """5xx: Lekto, or a proxy in front of it, failed."""


class WebhookVerificationError(LektoError):
    """A request to a webhook is not signed with its secret, or too old: do not trust it."""


class LektoVersionWarning(UserWarning):
    """Lekto speaks a version of its API whose requests or answers may differ from pylekto's."""
