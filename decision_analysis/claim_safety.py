"""Conservative release rules for uncalibrated football explanations.

These detect specific unsupported claims, not semantic truth. Rejection suppresses
the model prose; deterministic comparisons remain available.
"""
import re


def check_language(text):
    if not isinstance(text,str):raise ValueError('invalid_claim_text')
    rules={
        'uncalibrated_probability': r'[%％]|\b(?:probably|likely|unlikely|likelihood|probability|probabilities|odds|percent|per cent|chance of|chances of)\b|大概率|高概率|成功率(?:为|是|达到)|进球概率(?:为|是|达到)|百分之|十有八九',
        'unsupported_risk_strength': r'\b(?:high|huge|significant|substantial|very low|minimal)\s+(?:practical\s+)?risk\b|风险(?:很高|极高|很低|极低)|高风险|低风险',
        'unsupported_certainty': r'\b(?:definitely|certainly|guaranteed|guarantees|inevitably|optimal|safest|best choice)\b|\bwill\s+(?:score|intercept|win|lose|succeed|fail)\b|一定会|必然|肯定会|最优|最佳选择|必进|必丢',
        'invented_player_attribute': r'\b(?:left|right)[ -]footed\b|\b(?:is facing|faces the goal)\b|惯用脚(?:是|为)|身体(?:正)?朝向(?:左|右|球门)|他想要|他的意图是',
        'retrospective_outcome_claim': r'\b(?:was|has been)\s+intercepted\b|这次传球已被|随后进球|最终进球',
    }
    probability_text=re.sub(r'\b(?:not|no|without)\s+(?:(?:a|any|real|calibrated|verified|actual)\s+)*(?:probability|probabilities|odds|likelihood)\b','',text,flags=re.I)
    for code,pattern in rules.items():
        if re.search(pattern,probability_text if code=='uncalibrated_probability' else text,re.I):raise ValueError(code)


def check_estimate_scope(text):
    """Every model/hypothesis claim must name its scope and uncertainty."""
    scope=re.search(r'\b(?:model|simulation|simulated|hypothesis|hypothetical|assumption|assumptions)\b|模型|模拟|推演|假设',text,re.I)
    uncertain=re.search(r'\b(?:may|might|could|uncertain|unvalidated|estimate|estimates|hypothesis|hypothetical|assumption|assumptions)\b|可能|不确定|未经验证|估计|假设|不能确定',text,re.I)
    if not scope or not uncertain:raise ValueError('missing_model_scope_or_uncertainty')
