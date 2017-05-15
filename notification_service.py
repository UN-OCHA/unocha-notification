import smtplib
import requests
import json
import datetime
import dateutil.parser
import pytz
import pycountry

from twilio.rest import Client

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

from hdx.configuration import Configuration
from hdx.data.dataset import Dataset

TWILIO_ACCOUNT_SID = # TODO account sid goes here
TWILIO_AUTH_TOKEN = # TODO account auth token goes here

output_files = ["hr_info_contents.txt", "reliefweb_contents.txt", "fts_contents.txt", "hdx_contents.txt"]

# returns authentication token for hid api
def get_hid_json_web_token():
	hid_request_url = "https://api2.dev.humanitarian.id/api/v2/jsonwebtoken"
	hid_request_body = {
		"email": # TODO developer email,
		"password": # TODO developer password
	}
	result = requests.post(hid_request_url, hid_request_body).json()
	return result["token"]

# returns list of countries that a specific user is checked in to
def get_hid_checkin_countries_for(userid, webtoken):
	hid_request_url = "https://api2.dev.humanitarian.id/api/v2/user/" + userid
	headers = {'authorization': 'Bearer ' + webtoken}
	hid_data = requests.get(hid_request_url, headers=headers).json()
	countries = []
	if len(hid_data['operations']) != 0:
		for operation in hid_data['operations']:
			countries.append(operation['name'])
	return countries

# returns a list of Humanitarian ID user IDs of the users opted in
def get_users_opted_in(webtoken):
	# TODO, should use API call from humanitarian ID returning list of opted-in users
	# for testing, can set it up to return a singleton list of a developer's user id

# returns the email associated with the userid from Humanitarian ID
def get_email(userid, webtoken):
	hid_request_url = "https://api2.dev.humanitarian.id/api/v2/user/" + userid
	headers = {"authorization": "Bearer " + webtoken}
	hid_data = requests.get(hid_request_url, headers=headers).json()
	return hid_data["email"]

# uses bitly to create a short version of long_url
def generate_short_url(long_url):
	accessToken = # TODO bitly access token
	bitly_request = "https://api-ssl.bitly.com/v3/shorten?access_token=" + accessToken + "&longUrl=" + long_url
	bitly_data = requests.request("GET", bitly_request).json()
	return bitly_data["data"]["url"]

# gets information from reliefweb for a specific country between the two dates
def get_reliefweb_contents(country, from_iso, now_iso, urgent_only):
	numArticles = 0

	# "&filter[conditions][0][conditions][1][value][]=Situation Report" or something similar to be added to end
	reliefweb_request = "http://api.reliefweb.int/v1/reports?appname=apidoc&filter[operator]=AND&filter[conditions][0][field]=date.created&filter[conditions][0][value][from]=" + from_iso + "&filter[conditions][0][value][to]=" + now_iso + "&filter[conditions][1][field]=country&filter[conditions][1][value]=" + country
	#print reliefweb_request
	call_results = requests.request("GET", reliefweb_request)
	reliefweb_data = call_results.json()

	file = open("reliefweb_contents.txt", 'a')
	wrote_header = False
	if "data" in reliefweb_data and len(reliefweb_data["data"]) != 0:
		for content in reliefweb_data["data"]:
			article_info = requests.request("GET", content["href"].encode("utf-8")).json()
			title = content["fields"]["title"].encode("utf-8")
			if (urgent_only and ("Flash Update" in title or "Situation Report" in title)) or not urgent_only:
				if not wrote_header:
					file.write("<span style='font-size: 18px'>Latest updates on " + country + " from ReliefWeb: </span><br>")
					wrote_header = True
				if "file" in article_info["data"][0]["fields"]:
					link = article_info["data"][0]["fields"]["file"][0]["url"].encode("utf-8")
					file.write("<a href='" + link + "'><span style='font-size: 16px'>" + title+ "</span></a> <br>")
				else:
					file.write("<span style='font-size: 16px'>" + title + ": No link available. </span> <br>")
				if "body" in article_info["data"][0]["fields"]:
					body = article_info["data"][0]["fields"]["body"].encode("utf-8")
					body = body.replace("\n", "<br>")
					file.write("<p>" + body + "</p> <br><br>")
				
				numArticles += 1
				print "writing reliefweb"

			if "Flash Update" in title:
				sendTwilioSMS("Flash Update", country, "ReliefWeb", geenerate_short_url(link))
			elif "Situation Report" in title:
				sendTwilioSMS("Situation Report", country, "ReliefWeb", generate_short_url(link))
	file.close()

	return numArticles

# gets information on a specific country from reliefweb posted after a specific date
def get_hr_info_contents(country, from_iso, urgent_only):
	numArticles = 0

	# match country string to hr.info api country code
	location_id = -1
	hrinfo_locations = requests.request("GET", "https://www.humanitarianresponse.info/api/v1.0/locations").json()
	while "next" in hrinfo_locations and location_id == -1:
		for location in hrinfo_locations["data"]:
			if location["label"] == country:
				location_id = location["id"]
				break
		hrinfo_locations = requests.request("GET", hrinfo_locations["next"]["href"]).json()

	file = open("hr_info_contents.txt", 'a')

	if location_id != -1:
		# includes filtering information. Excludes unwanted document types:
		# Communication materials = 25
		# Training and Resource materials = 27
		# Policy and Guidance = 29
		# Contact List = 68
		# Data/Statistics = 67
		# Terms of Reference = 70
		# Note = 65
		# MOU = 69
		hrinfo_request = "https://www.humanitarianresponse.info/api/v1.0/documents?filter[locations]=" + str(location_id) + "&filter[publication_date][value]=" + from_iso + '&filter[publication_date][operator]=%22%3E=%22'
		if urgent_only:
			hrinfo_request += '&filter[document_type][value]=39&filter[document_type][operator]="=="'
		else:
			hrinfo_request += '&filter[document_type][value]=25&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=27&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=29filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=68&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=67&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=70&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=65&filter[document_type][operator]="!="'
			hrinfo_request += '&filter[document_type][value]=69&filter[document_type][operator]="!="'
		hrinfo_results = requests.request("GET", hrinfo_request)
		hrinfo_data = hrinfo_results.json()
		if "data" in hrinfo_data and len(hrinfo_data["data"]) > 0:
			file.write("<span style='font-size: 18px'> Latest updates on " + country.encode("utf-8") + " from HumanitarianResponse.info: </span> <br>")
			for content in hrinfo_data["data"]:
				title = content["label"]
				link = content["files"][0]["file"]["url"]
				file.write("<a href='" + link.encode("utf-8") + "'><span style='font-size: 16px'>" + title.encode("utf-8") + "</span></a> <br><br>")
				numArticles += 1
				print "writing hr.info"

				if "Flash Update" in title:
					sendTwilioSMS("Flash Update", country, "HR.info", geenerate_short_url(link))
				elif "Situation Report" in title:
					sendTwilioSMS("Situation Report", country, "HR.info", generate_short_url(link))
	file.close()
	return numArticles

# gets information on a specific country from fts posted after from_datetime and
# before to_datetime
def get_fts_contents(country, from_datetime, to_datetime):
	numArticles = 0
	countryISO3 = pycountry.countries.get(name=country).alpha_3
	year = from_datetime.year
	fts_request = "https://api.hpc.tools/v1/public/fts/flow?countryISO3=" + countryISO3 + "&year=" + str(year)
	fts_data = requests.request("GET", fts_request, auth=('mit_csail', 'xvn468sfhk')).json()
	file = open("fts_contents.txt", "a")
	wrote_header = False
	for flow in fts_data["data"]["flows"]:
		created_at_iso = flow["createdAt"]
		created_at_datetime = dateutil.parser.parse(created_at_iso)
		# check to see if the flow was created within the specified range
		if from_datetime.replace(tzinfo=None) <= created_at_datetime.replace(tzinfo=None) and to_datetime.replace(tzinfo=None) >= created_at_datetime.replace(tzinfo=None):
			if not wrote_header:
				file.write("<span style='font-size:18px'>Relevant New Flows relating to " + country + " on FTS</span><br><br>")
				wrote_header = True
			# get all necessary information from the result
			flow_url = "https://fts.unocha.org/flows/" + flow["id"]
			flow_type = flow["flowType"]
			if "originalAmount" in flow:
				flow_amount = flow["originalAmount"]
				if "originalCurrency" in flow:
					flow_currency = flow["originalCurrency"]
				else:
					flow_currency = ""
			else:
				flow_amount = flow["amountUSD"]
				flow_currency = "USD"
			flow_source_org = "Not specified"
			for flow_source in flow["sourceObjects"]:
				if flow_source["type"] == "Organization":
					flow_source_org = flow_source["name"]
			flow_dest_org = "Not specified"
			for flow_dest in flow["destinationObjects"]:
				if flow_dest["type"] == "Organization":
					flow_dest_org = flow_dest["name"]
			flow_date_datetime = dateutil.parser.parse(flow["date"])
			flow_date_readable = flow_date_datetime.strftime("%Y-%m-%d")
			flow_published = created_at_datetime.strftime("%Y-%m-%d")
			flow_description = flow["description"]

			# write response to file
			file.write("<br> <br> <br><a href='" + flow_url.encode("utf-8") + "'> <span style='font-size: 16px'>" + flow_type.encode("utf-8") + " Flow of " + str(flow_amount).encode("utf-8") + " " + flow_currency.encode("utf-8") + " from " + flow_source_org.encode("utf-8") + " to " + flow_dest_org.encode("utf-8") + "</span></a> <br><br>")
			file.write("<table> <tr> <th> Amount </th> <td>" + str(flow_amount).encode("utf-8") + " " + flow_currency.encode("utf-8") + "</td> </tr> <tr> <th> Source </th> <td>" + flow_source_org.encode("utf-8") + "</td> </tr> <tr> <th> Destination </th> <td>" + flow_dest_org.encode("utf-8") + "</td> </tr> <tr> <th> Flow Type </th> <td>" + flow_type.encode("utf-8") + "</td> </tr> <tr> <th> Transaction Date </th> <td>" + flow_date_readable.encode("utf-8") + "</td> </tr> <tr> <th> Flow Posted </th> <td>" + flow_published.encode("utf-8") + "</td> </tr> <tr> <th> Description </th> <td>" + flow_description.encode("utf-8") + "</td> </tr> </table>")
			#file.write("<i>The flow date is " + flow_date_readable.encode("utf-8") + " and it was published on " + flow_published.encode("utf-8") + ". </i><br><br>")
			#file.write(flow_description.encode("utf-8") + "<br><br>")

			print "writing fts"
			numArticles += 1
	file.close()
	return numArticles

# gets information on a specific country from hdx posted after from_datetime and
# before to_datetime
def get_hdx_contents(country, from_datetime, to_datetime):
	numArticles = 0
	config = Configuration.create(hdx_site='prod', hdx_read_only=True)

	datasets = Dataset.search_in_hdx(country, sort="metadata_modified desc", rows=1)

	file = open("hdx_contents.txt", "a")
	for dataset in datasets:
		file.write("<span style='font-size:16px'>Relevant New Dataset relating to " + country + " on HDX</span><br><br>")
		if dataset["url"]:
			file.write("<a href='" + str(dataset["url"]).encode("utf-8") + "''> <span style='font-size:16px'>" + str(dataset["title"]).encode("utf-8") + "</span> </a> <br>")
		else:
			file.write("<span style='font-size:16px'>" + str(dataset["title"]).encode("utf-8") + ": No Link Available.</span> <br>")
		file.write("<span style='font-size:14px'>" + dataset["notes"].encode("utf-8") + "</span>")
		numArticles += 1
		print "writing hdx"
	file.close()

	return numArticles


# gets content from all sources for the last 24 hours for a specific country
def get_contents_last_24_hrs(country):
	numArticles = 0
	now = datetime.datetime.now()
	day_ago = now - datetime.timedelta(days=1)
	month_ago = now - datetime.timedelta(days=31)
	month_ago_iso = month_ago.isoformat().split(".")[0]
	month_ago_iso += "%2B00:00"
	day_ago_iso = day_ago.isoformat().split(".")[0]
	day_ago_iso += "%2B00:00"
	now_iso = now.isoformat().split(".")[0]
	now_iso += "%2B00:00"

	numArticles += get_reliefweb_contents(country, day_ago_iso, now_iso, False)
	numArticles += get_hr_info_contents(country, day_ago_iso, False)
	numArticles += get_fts_contents(country, day_ago, now)
	numArticles += get_hdx_contents(country, day_ago, now)
	
	return numArticles

# Function for combining contents into one single email-able file
# filenames is an array containing the paths to the files
def combine_contents(filenames):
	outfile = open("all_contents.txt", "w")
	template_header = open("email_template_opener.txt")
	outfile.write(template_header.read())
	for fname in filenames:
		with open(fname) as infile:
			outfile.write(infile.read())
			outfile.write("<br>")
	template_closer = open("email_template_closer.txt")
	outfile.write(template_closer.read())

# sends a sendgrid email
def send_sendgrid_mail(contents_path, subject, who_from, to):
	server = smtplib.SMTP('smtp.sendgrid.net', 587)
	server.starttls()
	server.login() # TODO developer email, password are parameters

	fp = open(contents_path, 'rb')
	body = fp.read()
	fp.close()

	msg = MIMEMultipart()

	msg['Subject'] = subject
	msg['From'] = who_from
	msg['To'] = to
	msg.attach(MIMEText(body, 'html'))

	fp = open('UNOCHA.jpg', 'rb')
	msgImage = MIMEImage(fp.read())
	fp.close()

	msgImage.add_header('Content-ID', '<unocha>')
	msg.attach(msgImage)

	server.sendmail(who_from, to, msg.as_string())
	server.quit()
	print "sent mail"

# sends a single twilio text message
def sendTwilioSMS(report_type, country, source, link):
	client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
	# TODO to field is user's phone number, from field is developer Twilio phone number
	message = client.sms.messages.create(to="", from_="",
		body="ALERT - New " + report_type + " for " + country + " on " + source + " - " + link + " reply STOP to stop.")

# the standard notification sending method
def send_notifications():
	for user in get_users_opted_in(get_hid_json_web_token()):
		numArticles = 0
		# clear files to start over
		open("hr_info_contents.txt", "w").close()
		open("reliefweb_contents.txt", "w").close()
		open("fts_contents.txt", "w").close()
		open("hdx_contents.txt", "w").close()
		open("all_contents.txt", "w").close()
		for country in get_hid_checkin_countries_for(user, get_hid_json_web_token()):
			numArticles += get_contents_last_24_hrs(country)
		if numArticles != 0:
			combine_contents(output_files)
			# TODO 3rd parameter is email the content should be from
			send_sendgrid_mail("all_contents.txt", "Humanitarian Updates", "", get_email(user, get_hid_json_web_token()))

# sends only "urgent" notifications
def send_urgent_notifications():
	for user in get_users_opted_in(get_hid_json_web_token()):
		# clear files to start over
		open("hr_info_contents.txt", "w").close()
		open("reliefweb_contents.txt", "w").close()
		open("fts_contents.txt", "w").close()
		open("hdx_contents.txt", "w").close()
		open("all_contents.txt", "w").close()
		numArticles = 0
		for country in get_hid_checkin_countries_for(user, get_hid_json_web_token()):
			now = datetime.datetime.now()
			mapping = {}
			with open('last_email_mapping.txt', 'r') as file:
				mapping = eval(file.read())
				if user in mapping:
					then = mapping[user]
				else:
					then = now - datetime.timedelta(days=30)
				now_iso = now.isoformat().split(".")[0]
				now_iso += "%2B00:00"
				then_iso = then.isoformat().split(".")[0]
				then_iso += "%2B00:00"

				numArticles += get_reliefweb_contents(country, then_iso, now_iso, True)
				numArticles += get_hr_info_contents(country, then_iso, True)

		with open('last_email_mapping.txt', 'w') as file:
			mapping[user] = now
			file.write(str(mapping))

			if numArticles != 0:
				combine_contents(output_files)
				# TODO 3rd parameter is email the content should be from
				send_sendgrid_mail("all_contents.txt", "Urgent Humanitarian Updates", "", get_email(user, get_hid_json_web_token()))

				return numArticles

send_notifications()
