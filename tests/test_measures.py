import commons
import pandas as pd
from chatlas import Turn
from commons._provenance import TAG_EXTRA_KEY
from shinychat._chat_bookmark import serialize_chatlas_turn

from measures.microscopy import representative_well
from measures.results import ScientificImageResult, scientific_image_result


def test_representative_well_is_closest_to_median_then_well_id() -> None:
    rows = pd.DataFrame(
        {
            "well": ["D01", "A01", "B01", "C01"],
            "median_nuclear_gfp": [10.0, 8.0, 12.0, 30.0],
        }
    )
    assert representative_well(rows) == "B01"


def test_scientific_result_keeps_model_text_separate_from_serialized_image() -> None:
    result = scientific_image_result(
        value="Trusted numeric summary",
        image_base64="aW1hZ2U=",
        alt_text="An image",
        caption="A caption",
        extra={TAG_EXTRA_KEY: commons.Tag.A},
    )
    assert isinstance(result, ScientificImageResult)
    assert result.get_model_value() == "Trusted numeric summary"
    display = result.extra["display"]
    assert "data:image/png;base64,aW1hZ2U=" in str(display.html)
    assert result.extra[TAG_EXTRA_KEY] is commons.Tag.A

    saved = serialize_chatlas_turn(Turn([result], role="user"))
    assert (
        "data:image/png;base64,aW1hZ2U="
        in saved["contents"][0]["extra"]["display"]["html"]["html"]
    )
