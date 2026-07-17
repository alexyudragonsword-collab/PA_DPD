import numpy as np
import pytest

from padpd.waveform import qam_constellation, qam_demodulate, qam_modulate


@pytest.mark.parametrize("order", [4, 16, 64, 256, 1024, 4096])
def test_unit_average_power(order):
    c = qam_constellation(order)
    assert len(c) == order
    assert np.mean(np.abs(c) ** 2) == pytest.approx(1.0)


@pytest.mark.parametrize("order", [16, 256, 1024, 4096])
def test_modulate_demodulate_loopback(order):
    rng = np.random.default_rng(42)
    labels = rng.integers(0, order, size=10_000)
    points = qam_modulate(labels, order)
    recovered = qam_demodulate(points, order)
    np.testing.assert_array_equal(recovered, labels)


def test_demodulate_with_small_noise():
    order = 64
    rng = np.random.default_rng(1)
    labels = rng.integers(0, order, size=10_000)
    points = qam_modulate(labels, order)
    # noise well inside the decision distance for 64-QAM
    noisy = points + 0.01 * (rng.standard_normal(len(points))
                             + 1j * rng.standard_normal(len(points)))
    recovered = qam_demodulate(noisy, order)
    np.testing.assert_array_equal(recovered, labels)


def test_gray_neighbors_differ_by_one_bit():
    """Adjacent points on each axis must differ in exactly one bit."""
    order = 64
    m = 8
    c = qam_constellation(order)
    scale = np.sqrt((2 / 3) * (order - 1))
    grid = {}
    for k, p in enumerate(c):
        i = int(round((p.real * scale + (m - 1)) / 2))
        q = int(round((p.imag * scale + (m - 1)) / 2))
        grid[(i, q)] = k
    for (i, q), k in grid.items():
        for ni, nq in ((i + 1, q), (i, q + 1)):
            if (ni, nq) in grid:
                diff = k ^ grid[(ni, nq)]
                assert bin(diff).count("1") == 1
