from functools import singledispatch


__all__ = ["create_source", "create_reader", "BaseSource"]

class BaseSource:
    def documents(self):
        pass
    def transforms(self):
        pass

@singledispatch
def create_source(config):
    raise TypeError(f"Unsupported config type: {type(config)}")

@singledispatch
def create_reader(config):
    raise TypeError(f"Unsupported config type: {type(config)}")







