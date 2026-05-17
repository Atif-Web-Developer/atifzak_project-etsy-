from django.shortcuts import render

def calculator(request):
    return render(request, 'profit_pulse/calculator.html')
