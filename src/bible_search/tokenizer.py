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
        # kiwipiepy는 MeCab만 쓰는 경량 배포에서는 설치하지 않으므로,
        # 모듈 최상위가 아니라 여기서 import한다(MecabTokenizer도 동일).
        from kiwipiepy import Kiwi

        self._kiwi = Kiwi()

    def tokenize(self, text: str) -> list[str]:
        tokens = self._kiwi.tokenize(text)
        return [t.form.lower() for t in tokens if t.tag in self.CONTENT_TAGS]


class MecabTokenizer:
    """MeCab 기반 내용어 토크나이저 — KiwiTokenizer와 동일 인터페이스/태그 정책(세종 태그셋)."""

    CONTENT_TAGS: frozenset[str] = KiwiTokenizer.CONTENT_TAGS

    def __init__(self) -> None:
        import mecab_ko

        self._tagger = mecab_ko.Tagger()

    def tokenize(self, text: str) -> list[str]:
        out = []
        for line in self._tagger.parse(text).splitlines():
            if line == "EOS" or "\t" not in line:
                continue
            surface, feat = line.split("\t", 1)
            if feat.split(",", 1)[0] in self.CONTENT_TAGS:
                out.append(surface.lower())
        return out
