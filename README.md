---
title: BeeWeb
emoji: 💬
colorFrom: yellow
colorTo: purple
sdk: gradio
sdk_version: 5.0.1
app_file: app.py
pinned: false
license: mit
short_description: clientisde bee sdk
---

An example chatbot using [Gradio](https://gradio.app), [`huggingface_hub`](https://huggingface.co/docs/huggingface_hub/v0.22.2/en/index), and the [Hugging Face Inference API](https://huggingface.co/docs/api-inference/index).

![image](https://github.com/user-attachments/assets/6edfa78f-a928-4f05-b2c7-64234a0d314b)


## hosted

https://huggingface.co/spaces/swyx/BeeWeb?logs=build

## running 

```bash
gradio app.py
```

This will start your Gradio app with hot-reloading enabled. Now, whenever you make changes to your app.py file and save it, the server will automatically restart, and your changes will be reflected immediately in the browser.

Some additional tips:
- Make sure you're running this command from the directory containing your app.py file.
- If you want to specify a port, you can use: gradio app.py --port 8080 (replace 8080 with your desired port number).
- If you're developing locally and want to make your app accessible over your local network, you can add the --share flag: gradio app.py --share
