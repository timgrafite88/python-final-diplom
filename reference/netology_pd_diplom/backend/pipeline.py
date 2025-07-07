def save_profile(backend, user, response, *args, **kwargs):
    if backend.name == 'vk-oauth2':
        user.first_name = response.get('first_name', '')
        user.last_name = response.get('last_name', '')
        user.save()