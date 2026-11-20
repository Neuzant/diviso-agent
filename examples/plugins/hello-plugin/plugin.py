"""Example Diviso plugin: registers a `hello` tool."""


def hello(name: str = "world") -> str:
    return f"Hello, {name}! (from hello-plugin)"


def register(registry) -> None:
    registry.register("hello", hello, "Say hello (example plugin)")
