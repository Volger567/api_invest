from django.db import models


def is_proxy_instance(operation, operation_classes):
    if hasattr(operation_classes, '__iter__'):
        for operation_class in operation_classes:
            if operation.type in operation_class.possible_types:
                return operation_class
        return False
    return operation.type in operation_classes.possible_types


class ProxyInheritanceQuerySet(models.QuerySet):
    def filter_by_models(self, *_models):
        total_types = set()
        for model in _models:
            types = getattr(model, 'possible_types', None)
            if types is None or isinstance(types, str) and types != '__all__':
                raise ValueError(f'У всех переданных моделей должен быть указан possible_types')
            if types == '__all__':
                return self
            total_types |= set(types)
        return self.filter(type__in=total_types)


class ProxyInheritanceManager(models.Manager):
    def get_queryset(self):
        types = getattr(self.model, 'possible_types', None)
        if types is None or isinstance(types, str) and types != '__all__':
            raise ValueError(f'У модели {self.model} должен быть указан possible_types')
        if types == '__all__':
            type_filter = models.Q()
        else:
            type_filter = models.Q(type__in=types)
        qs = ProxyInheritanceQuerySet(self.model, using=self._db).filter(type_filter)
        return qs

    def filter_by_models(self, *args, **kwargs):
        return self.get_queryset().filter_by_models(*args, **kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        if getattr(self.model, 'is_abstract', False):
            raise ValueError('Класс является абстрактным, его экземпляр нельзя сохранить')
        for obj in objs:
            obj.type = obj.__class__.possible_types[0]
        super().bulk_create(objs, *args, **kwargs)
