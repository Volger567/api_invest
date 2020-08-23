# Tinkoff Investment
Сайт для сбора статистики с Тинькофф Инвестиций

**Backend:**
* **Python3.8**
* **Django3**
* **Docker**
* **PostgreSQL 12.3**
* **Gunicorn**
* **Nginx**

**Frontend:**
* **Шаблонизатор DTL**
* **Bootstrap4**
* **JQuery**

В дальнейшем планируется переписать на Vue.js, добавить Redis как брокера сообщений
(для отправки регистрационного письма и т.д)

Запуск
* Скопировать файл **backend/.env.example** в **backend/.env**
* Заполнить данными **backend/.env**
* Скопировать файл **docker-compose.yml.example** в **docker-compose.yml**
* Заполнить данными **docker-compose.yml**
* Выполнить `docker-compose up -d --build`
