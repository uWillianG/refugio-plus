from django.shortcuts import render
from django.views import View


class BookingView(View):
    @staticmethod
    def get(request):
        return render(request, 'booking.html')
