from .native import QualityResult


def apply_and_split(frame, config):
    """Select the declared adapter; optional DQX is imported only when used."""
    engine = config['quality']['engine']
    if engine == 'native':
        from .native import apply_and_split as implementation
    elif engine == 'dqx':
        from .dqx import apply_and_split as implementation
    else:
        raise NotImplementedError(f'quality.engine={engine} is not implemented')
    return implementation(frame, config)

__all__ = ["QualityResult", "apply_and_split"]
