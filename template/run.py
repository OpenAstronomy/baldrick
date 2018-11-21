import os

from baldrick import create_app

# Configure the App
app = create_app('<your-bot-name>')

# Bind to PORT if defined, otherwise default to 5000.
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, debug=False)
