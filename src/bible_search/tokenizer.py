from kiwipiepy import Kiwi


class KiwiTokenizer:
    # 내용어 품사만 유지: 명사류/용언류/부사/외래어·한자·숫자/어근
    CONTENT_TAGS: frozenset[str] = frozenset({
        "NNG", "NNP", "NNB", "NR", "NP",       # 명사류
        "VV", "VA", "VX", "VCP", "VCN",        # 용언류
        "MAG", "MAJ",                          # 부사류
        "SL", "SH", "SN",                      # 외래어/한자/숫자
        "XR",                                  # 어근
    })

    def __init__(self) -> None:
        self._kiwi = Kiwi()

    def tokenize(self, text: str) -> list[str]:
        tokens = self._kiwi.tokenize(text)
        return [t.form.lower() for t in tokens if t.tag in self.CONTENT_TAGS]
