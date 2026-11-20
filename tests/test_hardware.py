from diviso.hardware import (MODEL_SUGGESTIONS, HardwareInfo, check_model_fit,
                             model_size_gb, select_profile)


def hw(ram, gpu=None):
    return HardwareInfo(ram_gb=ram, cpu_count=4, gpu=gpu, ollama_running=False)


def test_profile_lite_for_low_ram():
    assert select_profile(hw(2)) == "lite"
    assert select_profile(hw(4)) == "lite"


def test_profile_balanced_for_mid_ram():
    assert select_profile(hw(8)) == "balanced"


def test_profile_pro_for_high_ram_or_gpu():
    assert select_profile(hw(32)) == "pro"
    assert select_profile(hw(4, gpu="NVIDIA Test")) == "pro"


def test_every_profile_has_suggestions():
    for profile in ("lite", "balanced", "pro"):
        assert MODEL_SUGGESTIONS[profile]


def test_model_size_parsing():
    assert model_size_gb("llama3.1:8b") == 5.0
    assert model_size_gb("unknown-model") is None


def test_small_model_fits_small_machine():
    fit = check_model_fit("llama3.2:1b", hw(4))
    assert fit.fits and fit.suggested_model == "llama3.2:1b"


def test_large_model_degrades_gracefully():
    fit = check_model_fit("llama3.1:70b", hw(4))
    assert not fit.fits
    assert model_size_gb(fit.suggested_model) <= 4 * 0.8
    assert "degrading" in fit.reason
