from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm
from django.core.mail import send_mail

def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_mail(
                'Welcome to Finance Advisor!',
                'Thank you for signing up. Please login to set up your 2FA.',
                'noreply@financeadvisor.local',
                [user.email],
                fail_silently=True,
            )
            return redirect('two_factor:login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def profile_view(request):
    return render(request, 'profile.html', {'user': request.user})
