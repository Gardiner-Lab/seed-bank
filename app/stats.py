"""
Segregation on selection plates: do the counts fit the ratio expected?

A T2 lot from a T1 plant with one insertion segregates 3 resistant : 1
sensitive; two unlinked insertions give 15 : 1; a homozygous line gives no
sensitive seedlings at all. The chi-square test (one degree of freedom) says
how well the counts fit a ratio: p below 0.05 means they do not.
"""

import math
from typing import Dict

RATIOS = {'3:1': (3, 1), '15:1': (15, 1), '1:0': (1, 0)}
MEANING = {'3:1': 'one insertion', '15:1': 'two unlinked insertions', '1:0': 'homozygous'}


def chi_square(resistant: int, sensitive: int, ratio: str) -> Dict:
    """The fit of the counts to one ratio: chi-square, p and what it means."""
    a, b = RATIOS[ratio]
    n = resistant + sensitive
    if n <= 0:
        return {'ratio': ratio, 'chi2': None, 'p': None, 'p_text': None, 'fits': None}
    if b == 0:
        # Homozygous: any sensitive seedling rules it out.
        return {'ratio': ratio, 'chi2': None, 'p': None, 'p_text': None, 'fits': sensitive == 0}
    exp_r, exp_s = n * a / (a + b), n * b / (a + b)
    chi2 = (resistant - exp_r) ** 2 / exp_r + (sensitive - exp_s) ** 2 / exp_s
    p = math.erfc(math.sqrt(chi2 / 2))
    return {'ratio': ratio, 'chi2': round(chi2, 3), 'p': round(p, 4), 'p_text': p_text(p), 'fits': p >= 0.05}


def p_text(p: float) -> str:
    """p as it is reported: very small values as an upper bound, not as 0."""
    return '< 0.0001' if p < 0.0001 else f'{p:.4f}'.rstrip('0').rstrip('.')


def assess(resistant: int, sensitive: int, expected: str) -> Dict:
    """Every ratio's fit, and a sentence on the one expected."""
    n = resistant + sensitive
    fits = {r: chi_square(resistant, sensitive, r) for r in RATIOS}
    chosen = fits[expected]
    share = f'{100 * resistant / n:.1f}% resistant' if n else 'no seedlings counted'
    if n == 0:
        verdict = 'No seedlings counted.'
    elif expected == '1:0':
        verdict = (f'Consistent with homozygous: no sensitive seedlings in {n}.' if chosen['fits']
                   else f'Not homozygous: {sensitive} of {n} seedlings were sensitive.')
    elif chosen['fits']:
        verdict = f'Consistent with {expected} ({MEANING[expected]}): χ² = {chosen["chi2"]}, p = {chosen["p_text"]}.'
    else:
        verdict = f'Differs from {expected} ({MEANING[expected]}): χ² = {chosen["chi2"]}, p {"" if chosen["p_text"].startswith("<") else "= "}{chosen["p_text"]}.'
    if n and n < 30:
        verdict += ' Few seedlings: count more for a reliable answer.'
    return {'n': n, 'share': share, 'fits': fits, 'verdict': verdict}
