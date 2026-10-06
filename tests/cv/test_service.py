import pytest
from fastapi.exceptions import RequestValidationError
from hypothesis import assume, given
from hypothesis import strategies as st

from app.cv.schemas import FormOption, FormOptionsResponse, GenerateRequest, SkillGroup
from app.cv.service import canonicalise_generate_request, generate_request_key, validate_generate_request

ids = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12)
id_lists = st.lists(ids, max_size=8)

requests = st.builds(GenerateRequest, title_id=ids, concept_ids=id_lists, skill_ids=id_lists)


@st.composite
def options_and_valid_request(draw: st.DrawFn) -> tuple[FormOptionsResponse, GenerateRequest]:
    titles = draw(st.lists(ids, min_size=1, max_size=5, unique=True))
    concepts = draw(st.lists(ids, max_size=5, unique=True))
    groups = draw(st.lists(st.lists(ids, min_size=1, max_size=4, unique=True), max_size=3))
    skills = [skill for group in groups for skill in group]

    options = FormOptionsResponse(
        titles=[FormOption(id=i, label=i) for i in titles],
        concepts=[FormOption(id=i, label=i) for i in concepts],
        skill_groups=[
            SkillGroup(id=f"group-{n}", label=f"Group {n}", skills=[FormOption(id=i, label=i) for i in group])
            for n, group in enumerate(groups)
        ],
    )
    request = GenerateRequest(
        title_id=draw(st.sampled_from(titles)),
        concept_ids=draw(st.lists(st.sampled_from(concepts), max_size=6)) if concepts else [],
        skill_ids=draw(st.lists(st.sampled_from(skills), max_size=6)) if skills else [],
    )
    return options, request


def unknown_to(options: FormOptionsResponse) -> st.SearchStrategy[str]:
    known = {o.id for o in options.titles + options.concepts} | {
        s.id for group in options.skill_groups for s in group.skills
    }
    return ids.filter(lambda i: i not in known)


@given(case=options_and_valid_request())
def test_known_ids_pass(case: tuple[FormOptionsResponse, GenerateRequest]) -> None:
    options, request = case

    validate_generate_request(request, options)


@given(case=options_and_valid_request(), data=st.data())
def test_unknown_ids_are_all_reported_at_their_position(
    case: tuple[FormOptionsResponse, GenerateRequest], data: st.DataObject
) -> None:
    options, request = case
    unknown = unknown_to(options)
    field = data.draw(st.sampled_from(["title_id", "concept_ids", "skill_ids"]))

    if field == "title_id":
        bad = request.model_copy(update={"title_id": data.draw(unknown)})
        expected_locs = {("body", "title_id")}
    else:
        values = list(getattr(request, field))
        positions = data.draw(st.sets(st.integers(0, len(values)), min_size=1))
        for position in sorted(positions):
            values.insert(position, data.draw(unknown))
        bad = request.model_copy(update={field: values})
        known = {o.id for o in options.concepts} | {s.id for g in options.skill_groups for s in g.skills}
        expected_locs = {("body", field, i) for i, value in enumerate(values) if value not in known}

    with pytest.raises(RequestValidationError) as raised:
        validate_generate_request(bad, options)

    assert {tuple(error["loc"]) for error in raised.value.errors()} == expected_locs


@given(request=requests, data=st.data())
def test_order_and_duplicates_do_not_change_the_key(request: GenerateRequest, data: st.DataObject) -> None:
    shuffled = GenerateRequest(
        title_id=request.title_id,
        concept_ids=data.draw(st.permutations(request.concept_ids + request.concept_ids[:1])),
        skill_ids=data.draw(st.permutations(request.skill_ids + request.skill_ids[:1])),
    )

    assert canonicalise_generate_request(shuffled) == canonicalise_generate_request(request)
    assert generate_request_key(canonicalise_generate_request(shuffled)) == generate_request_key(
        canonicalise_generate_request(request)
    )


@given(request=requests)
def test_canonicalising_is_idempotent(request: GenerateRequest) -> None:
    once = canonicalise_generate_request(request)

    assert canonicalise_generate_request(once) == once


@given(request=requests)
def test_canonicalising_keeps_the_selection(request: GenerateRequest) -> None:
    canonical = canonicalise_generate_request(request)

    assert canonical.title_id == request.title_id
    assert set(canonical.concept_ids) == set(request.concept_ids)
    assert set(canonical.skill_ids) == set(request.skill_ids)


@given(a=requests, b=requests)
def test_different_selections_get_different_keys(a: GenerateRequest, b: GenerateRequest) -> None:
    def selection(r: GenerateRequest) -> tuple[str, frozenset[str], frozenset[str]]:
        return r.title_id, frozenset(r.concept_ids), frozenset(r.skill_ids)

    assume(selection(a) != selection(b))

    assert generate_request_key(canonicalise_generate_request(a)) != generate_request_key(
        canonicalise_generate_request(b)
    )
