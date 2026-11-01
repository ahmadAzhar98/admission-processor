import io
import random
from collections.abc import Callable

import pytest
from common.schemas.documents import DocumentType
from PIL import Image

from synthetic import documents
from synthetic.identities import make_applicant
from synthetic.render import render


@pytest.fixture
def page_bytes() -> Callable[..., bytes]:
    """Return a factory rendering a synthetic page to PNG bytes."""

    def make(document_type: str = "fsc_result", transform=None) -> bytes:
        applicant = make_applicant(random.Random(1), ("Lahore",))
        content = documents.build_document(
            DocumentType(document_type), applicant, random.Random(2), "en"
        )
        image: Image.Image = render(content, random.Random(1))
        if transform is not None:
            image = transform(image)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    return make
