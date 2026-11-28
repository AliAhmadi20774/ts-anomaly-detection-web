from dataclasses import dataclass
from unittest import TestCase

from algorithms.runtimes.contracts import ModelRuntime
from algorithms.runtimes.registry import LoaderRegistry, default_registry


@dataclass(frozen=True)
class ExampleRuntime:
    algorithm_key: str
    features: tuple[str, ...]


def first_loader(source, *, architecture_params, input_spec):
    return ExampleRuntime("first", tuple(input_spec["features"]))


def second_loader(source, *, architecture_params, input_spec):
    return ExampleRuntime("second", tuple(input_spec["features"]))


class RuntimeRegistryTests(TestCase):
    def test_algorithms_resolve_to_their_own_loader(self):
        registry = LoaderRegistry()
        registry.register("first", first_loader)
        registry.register("second", second_loader)
        self.assertIs(registry.get_loader("first"), first_loader)
        self.assertIs(registry.get_loader("second"), second_loader)

    def test_unknown_algorithms_do_not_fall_back_to_another_model(self):
        with self.assertRaisesRegex(ValueError, "No model loader is registered.*unknown"):
            default_registry.get_loader("unknown")
        self.assertTrue(callable(default_registry.get_loader("lstm_ae")))

    def test_duplicate_registration_cannot_replace_a_loader(self):
        registry = LoaderRegistry()
        registry.register("first", first_loader)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register("first", second_loader)
        self.assertIs(registry.get_loader("first"), first_loader)

    def test_invalid_keys_are_rejected(self):
        for key in (None, "", "Upper", "bad.key", "3bad", "a" * 65, "bad\n"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                LoaderRegistry().register(key, first_loader)

    def test_non_callable_loaders_are_rejected(self):
        registry = LoaderRegistry()
        for loader in (None, 1, "a function", object()):
            with self.subTest(loader=loader), self.assertRaisesRegex(ValueError, "callable"):
                registry.register("first", loader)
        registry.register("first", first_loader)
        self.assertIs(registry.get_loader("first"), first_loader)

    def test_registries_do_not_share_mutable_registration_state(self):
        first, second = LoaderRegistry(), LoaderRegistry()
        first.register("example", first_loader)
        second.register("example", second_loader)
        self.assertIs(first.get_loader("example"), first_loader)
        self.assertIs(second.get_loader("example"), second_loader)

    def test_common_contract_does_not_require_a_torch_model(self):
        self.assertIsInstance(ExampleRuntime("example", ("pressure",)), ModelRuntime)
        self.assertNotIsInstance(object(), ModelRuntime)
