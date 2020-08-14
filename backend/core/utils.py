from django.db import models
from django.db.models import Q


class ProxyConstraintsError(Exception):
    pass


def _get_is_abstract_by_proxy_model(proxy_model):
    try:
        return getattr(proxy_model.proxy_constraints, proxy_model.__name__).is_abstract
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
    if hasattr(proxy_instances, '__iter__'):
        for proxy_instance in proxy_instances:
            if _model.type in _get_possible_types_by_proxy_model(proxy_instance):
                return proxy_instance
        return False
    return _model.type in _get_possible_types_by_proxy_model(proxy_instances)


class ProxyInheritanceQuerySet(models.QuerySet):
    def _filter_or_exclude(self, negate, *args, **kwargs):
        if 'proxy_instance_of' in kwargs or 'proxy_instance_of__exact' in kwargs:
            args = args + (ProxyQ(**kwargs), )
            kwargs = {}
        return super()._filter_or_exclude(negate, *args, **kwargs)


class ProxyInheritanceManager(models.Manager):
    def get_queryset(self):
        return ProxyInheritanceQuerySet(self.model, using=self._db).filter(ProxyQ(proxy_instance_of=self.model))

    def bulk_create(self, objs, *args, **kwargs):
        if _get_is_abstract_by_proxy_model(self.model):
            raise ValueError('Класс является абстрактным, его экземпляр нельзя сохранить')
        for obj in objs:
            obj.type = _get_possible_types_by_proxy_model(obj)[0]
        return super().bulk_create(objs, *args, **kwargs)

    def create(self, *args, **kwargs):
        if _get_is_abstract_by_proxy_model(self.model):
            raise ValueError('Класс является абстрактным, его экземпляр нельзя сохранить')
        return super().create(*args, **kwargs)


class ProxyQ(Q):
    def __init__(self, *args, _connector=None, _negated=False, **kwargs):
        if 'proxy_instance_of' in kwargs or 'proxy_instance_of__exact' in kwargs:
            proxy_instance_of = kwargs.pop('proxy_instance_of', ())
            if isinstance(proxy_instance_of, (list, tuple)):
                proxy_instance_of = tuple(proxy_instance_of)
            else:
                proxy_instance_of = (proxy_instance_of, )
            proxy_instance_of__exact = kwargs.pop('proxy_instance_of__exact', ())
            if isinstance(proxy_instance_of__exact, (list, tuple)):
                proxy_instance_of__exact = tuple(proxy_instance_of__exact)
            else:
                proxy_instance_of__exact = (proxy_instance_of__exact, )
            types = set()
            for proxy_instance in proxy_instance_of + proxy_instance_of__exact:
                types |= set(_get_possible_types_by_proxy_model(proxy_instance))
            kwargs['type__in'] = types
        super().__init__(*args, _connector=_connector, _negated=_negated, **kwargs)
