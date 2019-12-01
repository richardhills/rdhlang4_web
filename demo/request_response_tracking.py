from django.db.models.base import Model
from django.db.models.fields import CharField, IntegerField, DateTimeField, \
    TextField


class RequestResponse(Model):
    request_body = TextField()
    request_method = CharField(max_length=16)
    request_url = CharField(max_length=65536)
    timestamp = DateTimeField(auto_now_add=True)

    response_status_code = IntegerField()
    response_body = TextField()

    class Meta:
        app_label = "demo"

def request_response_middleware(get_response):
    def middleware(request):
        request_body = request.body
        response = get_response(request)
        if getattr(response, "_track_request_response", False) is True:
            RequestResponse.objects.create(
                request_body=request_body,
                request_method=request.method,
                request_url=request.get_full_path(),
                response_status_code=response.status_code,
                response_body=response.content
            )
        return response
    return middleware

class RequestResponseMixin(object):
    def dispatch(self, request, *args, **kwargs):
        result = super(RequestResponseMixin, self).dispatch(request, *args, **kwargs)
        result._track_request_response = True
        return result
