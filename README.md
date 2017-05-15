# unocha-notification
Code for notification service

# set up instructions
notification_service.py is the main service. It has TODOs throughout to fill in authentication information such as API keys and logins. Additionally, all of the python libraries must be imported with the most recent version in order for it to run.

# capabilities
The code is structured based on two main functions - send_notifications and send_urgent_notifications. They both use the methods which access particular services, such as get_reliefweb_contents, and pass a flag indicating whether or not to only return urgent content. These functions rely on the Humanitarian ID functions, in particular get_users_opted_in and get_email for personalization information. For formatting and sending the email, they use combine_contents (which combines the output files from each of the individual service's functions) and send_sendgrid_mail.

# cron job
The code should be best integrated by scheduling a cron job to call send_notifications every 24 hours and send_urgent_notifications as often as necessary to send near real-time messages.

# adding another data source
These steps describe how to add a theoretical service called "serviceX"
1. Write a function called get_serviceX_contents. This function should take in what country it should get information from, and a start and end time that it should search within, and a flag for whether or not to look for only urgent contents. Using API calls, it should collect the necessary information and format it into a file named serviceX_contents.txt. The function should count how many unique updates/articles it finds and return that number.
2. Add serviceX_contents.txt to the list output_files
3. Add a call to get_serviceX_contents in get_contents_last_24_hours
4. Add a call to get_serviceX_contents in send_urgent_notifications (if this service posts urgent content)
