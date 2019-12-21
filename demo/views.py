# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from json.encoder import JSONEncoder

from django.views.generic.base import TemplateView
from rest_framework.exceptions import ValidationError
from rest_framework.fields import JSONField, CharField, DictField
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from rdhlang4.exception_types import FatalException, PreparationException, \
    InvalidApplicationException
from rdhlang4.executor.executor import PreparedFunction, BreakException, \
    enforce_application_break_mode_constraints, jump_to_function
from rdhlang4.parser.rdhparser import parse, prepare_code
from rdhlang4.parser.visitor import type_op, ParseError
from rdhlang4.utils import NO_VALUE
from demo.request_response_tracking import RequestResponseMixin
from munch import munchify


class DemoView(TemplateView):
    template_name = "index.html"


class CodeSerializer(Serializer):
    code = CharField(style={'base_template': 'textarea.html'})

    def validate_code(self, code):
        try:
            code = prepare_code(code)
            enforce_application_break_mode_constraints(code)
            return code
        except ParseError as p:
            raise ValidationError("ParseError: {}".format(p.args), "parse-error")
        except PreparationException as p:
            raise ValidationError("PreparationException: {}".format(p.args), "preparation-error")
        except InvalidApplicationException as i:
            raise ValidationError("InvalidApplicationException: {}".format(i.args), "invalid-application-error")


class ValidationResponseSerializer(Serializer):
    break_modes = DictField(child=JSONField())
    opcode = JSONField()


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
            return repr(PreparedFunction)
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


class ExecutionView(RequestResponseMixin, GenericAPIView):
    serializer_class = CodeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(True)
        function = serializer.validated_data["code"]

        try:
            jump_to_function(function, NO_VALUE)
        except BreakException as b:
            if b.value is NO_VALUE:
                b.value = None
            return Response(data=ExecutionResponseSerializer(instance=munchify({
                "mode": b.mode,
                "value": json.loads(json.dumps(b.value, cls=ExecutionResponseJSONEncoder))
            })).data)
        except FatalException as f:
            print("FATAL ERROR")
            print(f)
            return Response(status=500)

class ValidationAndExecuteView(RequestResponseMixin, GenericAPIView):
    serializer_class = CodeSerializer

    def post(self, request):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(True)
            function = serializer.validated_data["code"]

            jump_to_function(function, NO_VALUE)
        except BreakException as b:
            if b.value is NO_VALUE:
                b.value = None

            break_types = function.break_types

            return Response(data=ValidationAndExecutionResponseSerializer(instance=munchify({
                "validation": {
                    "break_modes": { m: t.to_dict() for m, t in break_types.items() },
                    "opcode": function.data
                },
                "execution": {
                    "mode": b.mode,
                    "value": json.loads(json.dumps(b.value, cls=ExecutionResponseJSONEncoder))
                }
            })).data)
        except FatalException as f:
            print("FATAL ERROR")
            print(f)
            return Response(status=500)
