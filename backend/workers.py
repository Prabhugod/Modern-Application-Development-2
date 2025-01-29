# from celery import Celery
# # from flask import current_app as app
# from app import app

# celery = Celery("Application Jobs")

# class ContextTask(celery.Task):
#     def __call__(self, *args, **kwargs):
#         with app.app_context():
#             return self.run(*args, **kwargs)

from celery import Celery

def make_celery(app):
    celery = Celery(
        app.import_name,
        BROKER_URL=app.config['CELERY_BROKER_URL'], 
        RESULT_BACKEND = app.config["CELERY_RESULT_BACKEND"]
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# celery = workers.celery
# celery.conf.update(BROKER_URL = app.config['CELERY_BROKER_URL'], RESULT_BACKEND = app.config["CELERY_RESULT_BACKEND"])
# celery.Task = workers.ContextTask
# app.app_context().push()