import openai, concurrent.futures
mro = [c.__name__ for c in openai.APITimeoutError.__mro__]
print("MRO:", mro)
print("Inherits TimeoutError:", "TimeoutError" in mro)
print("Is TimeoutError subclass:", issubclass(openai.APITimeoutError, TimeoutError))
print("concurrent.futures.TimeoutError is TimeoutError:", concurrent.futures.TimeoutError is TimeoutError)
