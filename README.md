# FunkoBot

### Primary source of crypto software and topics - [Web3 Enjoyer](https://t.me/+oeLEbd7IVig0ZGMy)

## What is bot doing?

1. Login

![image](https://user-images.githubusercontent.com/58307006/218306789-06ee35de-4be1-4d31-89cc-8bfdc53b94dc.png)

2. Waits for a button in the queue and clicks on it

![image](https://user-images.githubusercontent.com/58307006/218306784-d260da6c-98aa-463c-a7d1-160d662d57a1.png)

3. Passes captcha from drops

![image](https://user-images.githubusercontent.com/58307006/218306781-3872c791-3f54-4e06-98f5-b22a50d8a6c1.png)

4. Recaptcha passes

![image](https://user-images.githubusercontent.com/58307006/218306779-81f1db45-761b-4d49-b172-2a23b76bb6a0.png)

5. Checks accounts and closes those where the queue is long (more than 30 minutes for example)

![image](https://user-images.githubusercontent.com/58307006/218306774-fb65f945-4f46-4a11-982a-f7e16036ce4a.png)

## How to use?

#### In config.txt:
- sale_link - snares for sale funko - https://digital.funko.com/drop/108/nicktoons-series-2/
- max_queue_time - maximum queue time in minutes
- TWOCAPTCHA_API_KEY - 2 captcha key
  
#### In accounts.txt - line by line login and password and proxy in the format:
- login|password|proxy
- login|password
- or if no proxy

### To run, write to the console python funko.py