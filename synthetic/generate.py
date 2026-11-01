"""Generate a synthetic dataset for one or more tenants.

Usage::

    python -m synthetic.generate --seed 42 --applications 20 --out synthetic/output

For every tenant, each application gets the tenant's required documents
for one fictional applicant. Some get a planted name mismatch, then each
document is rendered and degraded. Images, per-document JSON labels and
a ``manifest.jsonl`` are written under ``--out``.
"""

import argparse
import logging
import random
from dataclasses import replace
from pathlib import Path

from common.log import configure_logging
from common.schemas.documents import DocumentType
from common.tenant_config.loader import TenantRegistry
from common.tenant_config.models import TenantConfig

from synthetic import augment
from synthetic.documents import DocumentContent, build_document
from synthetic.identities import Applicant, make_applicant
from synthetic.labels import GroundTruth, InjectedMismatch, write_manifest
from synthetic.render import render

logger = logging.getLogger(__name__)

# Mostly Punjab districts, with a few from elsewhere so domicile rules fail.
DISTRICTS = (
    "Lahore", "Lahore", "Kasur", "Sheikhupura", "Gujranwala", "Faisalabad",
    "Rawalpindi", "Multan", "Sialkot", "Okara", "Karachi South", "Peshawar",
)  # fmt: skip
MISMATCH_RATE = 0.1
B_FORM_RATE = 0.1


def perturb_name(name: str, rng: random.Random) -> str:
    """Return a plausible misspelling: swap, drop or double one letter."""
    letters = list(name)
    positions = [
        i for i, ch in enumerate(letters[:-1]) if ch.isalpha() and letters[i + 1].isalpha()
    ]
    i = rng.choice(positions)
    action = rng.choice(("swap", "drop", "double"))
    if action == "swap":
        letters[i], letters[i + 1] = letters[i + 1], letters[i]
    elif action == "drop":
        del letters[i]
    else:
        letters.insert(i, letters[i])
    altered = "".join(letters)
    return altered if altered != name else name + "a"


def required_types(config: TenantConfig, rng: random.Random) -> list[DocumentType]:
    """Pick the document types one application submits for ``config``."""
    chosen = []
    for req in config.documents:
        if not req.required:
            continue
        if req.alternatives and rng.random() < B_FORM_RATE:
            chosen.append(req.alternatives[0])
        else:
            chosen.append(req.type)
    return chosen


def language_for(config: TenantConfig, rng: random.Random) -> str:
    """Draw a document language, biased towards the tenant's default."""
    if config.notifications.default_language == "ur":
        return rng.choice(("ur", "ur", "mixed", "en"))
    return rng.choice(("en", "en", "mixed", "ur"))


def _mismatch(
    contents: list[DocumentContent], rng: random.Random
) -> tuple[list[DocumentContent], InjectedMismatch | None]:
    candidates = [i for i, c in enumerate(contents) if "full_name" in c.fields]
    if len(candidates) < 2 or rng.random() >= MISMATCH_RATE:
        return contents, None
    index = rng.choice(candidates[1:])
    target = contents[index]
    original = str(target.fields["full_name"])
    altered = perturb_name(original, rng)
    fields = {**target.fields, "full_name": altered}
    lines = [(lbl, altered if val == original else val) for lbl, val in target.lines]
    contents = list(contents)
    contents[index] = replace(target, fields=fields, lines=lines)
    return contents, InjectedMismatch(
        document_type=target.document_type, field="full_name", original=original, altered=altered
    )


def generate_application(
    config: TenantConfig, index: int, seed: int, out_dir: Path | None
) -> list[GroundTruth]:
    """Generate all documents of one application and optionally write images.

    RNGs are derived from ``(seed, tenant, index)`` so adding tenants or
    applications never changes previously generated ones. Content and
    pixels use separate RNGs, so labels are identical with or without
    rendering images.
    """
    rng = random.Random(f"{seed}:{config.tenant_id}:{index}")
    applicant: Applicant = make_applicant(rng, DISTRICTS)
    application_id = f"app-{index:05d}"
    contents = [
        build_document(t, applicant, rng, language_for(config, rng))
        for t in required_types(config, rng)
    ]
    contents, mismatch = _mismatch(contents, rng)
    labels = []
    for number, content in enumerate(contents):
        document_id = f"{application_id}-{number:02d}-{content.document_type.value}"
        image_rng = random.Random(f"{seed}:{config.tenant_id}:{index}:{number}:image")
        profile, names = augment.choose_augmentations(image_rng)
        image_path = None
        applied: list[dict[str, object]] = []
        if out_dir is not None:
            image, applied = augment.apply(render(content, image_rng), image_rng, names)
            folder = out_dir / config.tenant_id / application_id
            folder.mkdir(parents=True, exist_ok=True)
            image.save(folder / f"{document_id}.png")
            image_path = str((folder / f"{document_id}.png").relative_to(out_dir))
        label = GroundTruth(
            tenant_id=config.tenant_id,
            application_id=application_id,
            document_id=document_id,
            document_type=content.document_type,
            language=content.language,
            layout=content.layout,
            fields=content.fields,
            text=content.text,
            profile=profile,
            augmentations=applied,
            expected_reupload=augment.is_severe(applied),
            injected_mismatch=mismatch
            if mismatch and mismatch.document_type == content.document_type
            else None,
            image_path=image_path,
        )
        if out_dir is not None:
            (out_dir / config.tenant_id / application_id / f"{document_id}.json").write_text(
                label.model_dump_json(indent=2), encoding="utf-8"
            )
        labels.append(label)
    return labels


def generate(
    registry: TenantRegistry,
    tenant_ids: list[str],
    applications: int,
    seed: int,
    out_dir: Path | None,
) -> list[GroundTruth]:
    """Generate ``applications`` applications for each tenant."""
    labels: list[GroundTruth] = []
    for tenant_id in tenant_ids:
        config = registry.get(tenant_id)
        for index in range(applications):
            labels.extend(generate_application(config, index, seed, out_dir))
    if out_dir is not None:
        write_manifest(labels, out_dir)
    return labels


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--applications", type=int, default=10, help="per tenant")
    parser.add_argument("--tenant", action="append", help="repeatable; default all")
    parser.add_argument("--tenants-dir", type=Path, default=Path("tenants"))
    parser.add_argument("--out", type=Path, default=Path("synthetic/output"))
    args = parser.parse_args(argv)
    configure_logging()
    registry = TenantRegistry(args.tenants_dir)
    tenant_ids = args.tenant or registry.tenant_ids()
    args.out.mkdir(parents=True, exist_ok=True)
    labels = generate(registry, tenant_ids, args.applications, args.seed, args.out)
    logger.info("dataset generated", extra={"documents": len(labels), "out": str(args.out)})


if __name__ == "__main__":
    main()
