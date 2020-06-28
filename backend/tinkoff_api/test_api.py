import pytest

from tinkoff_api import TinkoffProfile


class TestTinkoffApiPermission:
    @pytest.fixture(autouse=True, scope='class')
    def init(self):
        pass

    def test_init_no_token(self):
        with pytest.raises(TypeError):
            TinkoffProfile()

    def test_init_auth(self):
        assert not TinkoffProfile('something').is_sandbox_token_valid
        assert not TinkoffProfile('something').is_production_token_valid
        assert not TinkoffProfile('something').is_authorized

