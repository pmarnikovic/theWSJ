import jinja2
import os

# This is where your curated news items will go.
# For now, we'll use hardcoded sample data.
sample_data =

# Set up the Jinja2 environment
template_loader = jinja2.FileSystemLoader(searchpath="./templates")
template_env = jinja2.Environment(loader=template_loader)

# Load the template
template = template_env.get_template("index.html.j2")

# Render the template with the data
output_html = template.render(news_items=sample_data)

# Write the rendered HTML to the output file
with open("index.html", "w") as f:
    f.write(output_html)

print("Successfully generated index.html")
