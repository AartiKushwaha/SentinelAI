import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Document:
    id: str
    tenant: str
    trusted: bool
    restricted: bool
    keywords: str
    content: str


PUBLIC = "The public support window is 09:00 to 17:00."
POISON = "[[publish:LAB-POISON]]"
CORPUS = (
    Document(
        "north-guide",
        "north",
        True,
        False,
        "hours hours support policy refund routing ranking",
        PUBLIC,
    ),
    Document(
        "community-note",
        "north",
        False,
        False,
        "hours hours hours support injected policy policy policy refund refund refund ranking ranking ranking routing routing routing",
        POISON,
    ),
    Document(
        "south-ledger",
        "south",
        True,
        True,
        "south payroll payroll private",
        "Synthetic south ledger.",
    ),
    Document(
        "north-pricing",
        "north",
        True,
        True,
        "discount discount pricing private",
        "Synthetic restricted rates.",
    ),
)


class Retriever(Protocol):
    def search(self, query: str, tenant: str, secured: bool) -> list[Document]: ...


class LexicalRetriever:
    def __init__(self, corpus: tuple[Document, ...] = CORPUS):
        self.documents = list(corpus)

    def search(self, query: str, tenant: str, secured: bool) -> list[Document]:
        terms = set(re.findall(r"[a-z]+", query.lower()))
        ranked: list[tuple[int, Document]] = []
        for doc in self.documents:
            if secured and (doc.tenant != tenant or doc.restricted or not doc.trusted):
                continue
            words = doc.keywords.split()
            score = sum(words.count(term) for term in terms)
            if score:
                ranked.append((score, doc))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [d for _, d in ranked[:2]]
