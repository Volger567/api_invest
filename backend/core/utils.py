from django.db import models
from django.db.models import Q


class ProxyConstraintsError(Exception):
    pass


def _get_is_abstract_by_proxy_model(proxy_model, raise_exception=False):
    try:
        is_abstract = getattr(proxy_model.proxy_constraints, proxy_model.__name__).is_abstract
        if is_abstract and raise_exception:
            raise ValueError('Класс является абстрактным, его экземпляр нельзя сохранить')
        return is_abstract
    except AttributeError:
        return False


def _get_possible_types_by_proxy_model(proxy_model):
    if hasattr(proxy_model, 'proxy_constraints'):
        if hasattr(proxy_model.proxy_constraints, proxy_model.__name__):
            possible_types = getattr(getattr(proxy_model.proxy_constraints, proxy_model.__name__), 'possible_types')
            if possible_types is None:
                raise ProxyConstraintsError(
                    f'В proxy_constraints модели {proxy_model} не определен {proxy_model}.possible_types'
                )
            elif isinstance(possible_types, (list, tuple)):
                return possible_types
            else:
                raise ProxyConstraintsError(
                    f'В proxy_constraints модели {proxy_model}, '
                    f'{proxy_model}.possible_types должен быть типа list/tuple'
                )
        else:
            raise ProxyConstraintsError(f'В proxy_constraints модели {proxy_model} не определен класс {proxy_model}')
    else:
        raise ProxyConstraintsError(f'В модели {proxy_model} не определен proxy_constraints')


def is_proxy_instance(_model, proxy_instances):
    if isinstance(proxy_instances, (tuple, list)):
        for proxy_instance in proxy_instances:
            if _model.type in _get_possible_types_by_proxy_model(proxy_instance):
                return proxy_instance
        return False
    return _model.type in _get_possible_types_by_proxy_model(proxy_instances)


class ProxyInheritanceQuerySet(models.QuerySet):
    def _filter_or_exclude(self, negate, *args, **kwargs):
        args = args + (ProxyQ(**kwargs), )
        kwargs = {}
        return super()._filter_or_exclude(negate, *args, **kwargs)


class ProxyInheritanceManager(models.Manager):
    def get_queryset(self):
        return ProxyInheritanceQuerySet(self.model, using=self._db).filter(ProxyQ(proxy_instance_of=self.model))

    def bulk_create(self, objs, *args, **kwargs):
        _get_is_abstract_by_proxy_model(self.model, raise_exception=True)
        for obj in objs:
            obj.type = _get_possible_types_by_proxy_model(obj.__class__)[0]
        return super().bulk_create(objs, *args, **kwargs)

    def create(self, *args, **kwargs):
        _get_is_abstract_by_proxy_model(self.model, raise_exception=True)
        kwargs['type'] = _get_possible_types_by_proxy_model(self.model)[0]
        return super().create(*args, **kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        _get_is_abstract_by_proxy_model(self.model, raise_exception=True)
        kwargs['type__in'] = _get_possible_types_by_proxy_model(self.model)
        defaults = defaults or {}
        defaults.setdefault('type', kwargs['type__in'][0])
        return super().update_or_create(defaults, **kwargs)


class ProxyQ(Q):
    def __init__(self, *args, _connector=None, _negated=False, **kwargs):
        for kwarg in kwargs.copy():
            is_proxy_kwarg = (
                kwarg == 'proxy_instance_of' or
                kwarg.endswith('__proxy_instance_of') and kwarg.count('proxy_instance_of') == 1
            )
            if is_proxy_kwarg:
                proxy_instance_of = kwargs.pop(kwarg)
                if isinstance(proxy_instance_of, (list, tuple)):
                    proxy_instance_of = tuple(proxy_instance_of)
                else:
                    proxy_instance_of = (proxy_instance_of, )
                types = set()
                for proxy_instance in proxy_instance_of:
                    types |= set(_get_possible_types_by_proxy_model(proxy_instance))
                kwargs[kwarg.replace('proxy_instance_of', 'type__in')] = types
        super().__init__(*args, _connector=_connector, _negated=_negated, **kwargs)
