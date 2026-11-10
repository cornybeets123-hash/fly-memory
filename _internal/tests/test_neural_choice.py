"""The real neural readout varies, responds to input, and has no tie-break."""

from _internal.maze.kernel import Kernel
from _internal.maze.workshop_world import WorkshopWorld
from fly_brain import FlyBrain


def test_neural_option_selection_and_readout_controls():
    choices = set()
    with Kernel() as kernel:
        for seed in (100, 104, 108):
            for rates in ((30, 30), (0, 30), (30, 0)):
                session = f"test:{seed}:{rates}"
                brain = FlyBrain(kernel, session, seed)
                for _ in range(10):
                    _, _, neural = brain.step(0, options=rates)
                choice = brain.select(neural, [0, 1])
                assert choice is not None
                if rates == (30, 30):
                    choices.add(choice)
                else:
                    assert choice == (1 if rates[0] == 0 else 0)
                assert brain.select(neural, [0, 1], mute=True) is None
                assert brain.select(neural, [0, 1], reverse=True) == 1 - choice
                kernel.drop(session)
    assert choices == {0, 1}


def test_spawn_and_visible_return_line():
    world = WorkshopWorld()
    assert len(world.openings(*world.launch)) == 1
    assert world.start_line == (220, 300, 500)
    assert not world.returned_to_start(*world.launch[:2])
    assert world.returned_to_start(260, 500)
    assert not world.free(320, 620)
