from civilpy.structural.steel import hello_world


def test_helloworld_no_params():
    assert hello_world() == "Hello World!"


def test_hello_world_with_param():
    assert hello_world("Everyone") == "Hello Everyone!"
