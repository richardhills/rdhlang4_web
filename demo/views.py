# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from json.encoder import JSONEncoder
import traceback

from django.views.generic.base import TemplateView
from munch import munchify
from rest_framework.exceptions import ValidationError
from rest_framework.fields import JSONField, CharField, DictField
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from demo.request_response_tracking import RequestResponseMixin
from rdhlang4.exception_types import FatalException, PreparationException, \
    InvalidApplicationException
from rdhlang4.executor.executor import PreparedFunction, BreakException, \
    enforce_application_break_mode_constraints, jump_to_function
from rdhlang4.parser.rdhparser import parse, prepare_code
from rdhlang4.parser.visitor import type_op, ParseError
from rdhlang4.type_system.values import List, Object
from rdhlang4.utils import NO_VALUE


class DemoView(TemplateView):
    template_name = "index.html"


class CodeSerializer(Serializer):
    code = CharField(style={'base_template': 'textarea.html'})

    def validate_code(self, code):
        try:
            return prepare_code(code)
        except ParseError as p:
            raise ValidationError("ParseError: {}".format(p.args), "parse-error")
        except PreparationException as p:
            raise ValidationError("PreparationException: {}".format(p.args), "preparation-error")
        except InvalidApplicationException as i:
            raise ValidationError("InvalidApplicationException: {}".format(i.args), "invalid-application-error")


class ValidationResponseSerializer(Serializer):
    break_modes = DictField(child=JSONField())
    ast = JSONField()


class ExecutionResponseSerializer(Serializer):
    mode = CharField()
    value = JSONField()

class ValidationAndExecutionResponseSerializer(Serializer):
    validation = ValidationResponseSerializer()
    execution = ExecutionResponseSerializer()

class ExecutionResponseJSONEncoder(JSONEncoder):
    def default(self, value):
        if value == NO_VALUE:
            return None
        if isinstance(value, PreparedFunction):
            return value.data
        if isinstance(value, List):
            return value.wrapped
        if isinstance(value, Object):
            return dict(value)
        return super(ExecutionResponseJSONEncoder, self).default(value)

class ValidationView(RequestResponseMixin, GenericAPIView):
    serializer_class = CodeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(True)
        function = serializer.validated_data["code"]

        break_types = function.break_types

        return Response(data=ValidationResponseSerializer(
            instance={
                "break_modes": { m: t.to_dict() for m, t in break_types.items() },
                "opcode": function.data
            }
        ).data)

def make_safe_for_json_serialization(data):
    return json.loads(json.dumps(data, cls=ExecutionResponseJSONEncoder))

class ValidationAndExecuteView(RequestResponseMixin, GenericAPIView):
    serializer_class = CodeSerializer

    def post(self, request):
        break_types = None
        break_result = None
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(True)
            potential_function = serializer.validated_data["code"]

            if isinstance(potential_function, PreparedFunction):
                break_types = potential_function.break_types
                jump_to_function(potential_function, NO_VALUE)
        except BreakException as b:
            if b.value is NO_VALUE:
                b.value = None

            break_result = b
        except FatalException as f:
            print("FATAL ERROR")
            traceback.print_exc()
            print(f)
            return Response(status=500)

        return Response(data=ValidationAndExecutionResponseSerializer(instance=munchify({
            "validation": {
                "break_modes": { m: t.to_dict() for m, t in break_types.items() } if break_types else {},
                "ast": make_safe_for_json_serialization(potential_function)
            },
            "execution": {
                "mode": break_result.mode,
                "value": make_safe_for_json_serialization(break_result.value)
            } if break_result else None
        })).data)
