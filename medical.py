from flask import Flask, request, jsonify,render_template,session
from openai import OpenAI
import json
import uuid
import os
app = Flask(__name__)

token = "paste API key"
endpoint = "https://models.inference.ai.azure.com"
model_name = "gpt-4o-mini"
app.secret_key = os.urandom(24)
client = OpenAI(
    base_url=endpoint,
    api_key=token,
)


doctors = {
    "Dr. Smith": {"specialty": "Cardiologist", "clinic": "Heart Care Center"},
    "Dr. Johnson": {"specialty": "Dermatologist", "clinic": "Skin Health Clinic"},
}

clinics = {
    "Heart Care Center": {
        "location": "123 Main St, Cityville",
        "timings": "Mon-Fri: 9AM-5PM",
    },
    "Skin Health Clinic": {
        "location": "456 Oak Rd, Townsburg",
        "timings": "Mon-Sat: 10AM-6PM",
    },
}

available_slots = {
    "Dr. Smith": {
        "2023-07-01": ["10:00", "11:00", "14:00", "15:00"],
        "2023-07-02": ["09:00", "10:00", "11:00", "14:00"],
    },
    "Dr. Johnson": {
        "2023-07-01": ["11:00", "13:00", "14:00", "16:00"],
        "2023-07-02": ["10:00", "12:00", "15:00", "16:00"],
    },
}

appointments = []

def get_doctor_info(doctor_name):
    return doctors.get(doctor_name, "Doctor not found")

def get_clinic_info(clinic_name):
    return clinics.get(clinic_name, "Clinic not found")

def check_availability(doctor_name, date):
    return available_slots.get(doctor_name, {}).get(date, [])

def book_appointment(doctor_name, date, time, patient_name, patient_email):
    if doctor_name in available_slots and date in available_slots[doctor_name] and time in available_slots[doctor_name][date]:
        available_slots[doctor_name][date].remove(time)
        appointments.append({
            "doctor": doctor_name,
            "date": date,
            "time": time,
            "patient_name": patient_name,
            "patient_email": patient_email
        })
        return True
    return False


functions = [
    {
        "name": "get_doctor_info",
        "description": "Get information about a specific doctor",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor"
                }
            },
            "required": ["doctor_name"]
        }
    },
    {
        "name": "get_clinic_info",
        "description": "Get information about a specific clinic",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_name": {
                    "type": "string",
                    "description": "The name of the clinic"
                }
            },
            "required": ["clinic_name"]
        }
    },
    {
        "name": "check_availability",
        "description": "Check available time slots for a given doctor and date",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor"
                },
                "date": {
                    "type": "string",
                    "description": "The date to check availability for, in YYYY-MM-DD format"
                }
            },
            "required": ["doctor_name", "date"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment with a doctor",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor"
                },
                "date": {
                    "type": "string",
                    "description": "The date for the appointment, in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "The time for the appointment, in HH:MM format"
                },
                "patient_name": {
                    "type": "string",
                    "description": "The name of the patient"
                },
                "patient_email": {
                    "type": "string",
                    "description": "The email of the patient"
                }
            },
            "required": ["doctor_name", "date", "time", "patient_name", "patient_email"]
        }
    }
]

@app.route('/')
def home():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    if 'messages' not in session:
        session['messages'] = [
            {
                "role": "system",
                "content": """You are a helpful medical assistant that can provide information about doctors and clinics, and handle appointment bookings. Follow this conversation flow:

1. Start with a generic greeting and ask how you can help.
2. When the user mentions a health issue, ask for more details about their symptoms or concerns.
3. Based on the user's issue, recommend an appropriate doctor or specialist.
4. If the user wants to book an appointment, ask for their name and email.
5. Once you have the name and email, check the doctor's availability and suggest available time slots.
6. Confirm the appointment details before finalizing the booking.

Remember to be empathetic and professional throughout the conversation."""
            }
        ]
    return render_template('index1.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    
    session['messages'].append({"role": "user", "content": user_message})
    
    response = client.chat.completions.create(
        messages=session['messages'],
        temperature=1.0,
        top_p=1.0,
        max_tokens=1000,
        model=model_name,
        functions=functions,
        function_call="auto"
    )

    response_message = response.choices[0].message

    if response_message.function_call:
        function_name = response_message.function_call.name
        function_args = json.loads(response_message.function_call.arguments)
        
        if function_name == "get_doctor_info":
            function_response = get_doctor_info(function_args['doctor_name'])
        elif function_name == "get_clinic_info":
            function_response = get_clinic_info(function_args['clinic_name'])
        elif function_name == "check_availability":
            available_times = check_availability(function_args['doctor_name'], function_args['date'])
            function_response = f"Available times for Dr. {function_args['doctor_name']} on {function_args['date']}: {', '.join(available_times)}"
        elif function_name == "book_appointment":
            success = book_appointment(
                function_args['doctor_name'],
                function_args['date'],
                function_args['time'],
                function_args['patient_name'],
                function_args['patient_email']
            )
            function_response = "Appointment booked successfully!" if success else "Sorry, that time slot is not available."
        
        session['messages'].append(response_message)
        session['messages'].append(
            {
                "role": "function",
                "name": function_name,
                "content": json.dumps(function_response),
            }
        )
        
        second_response = client.chat.completions.create(
            messages=session['messages'],
            temperature=1.0,
            top_p=1.0,
            max_tokens=1000,
            model=model_name
        )
        
        bot_response = second_response.choices[0].message.content
    else:
        bot_response = response_message.content
    
    session['messages'].append({"role": "assistant", "content": bot_response})
    
    if len(session['messages']) > 10: 
        session['messages'] = session['messages'][-10:]
    
    session.modified = True
    
    return jsonify({"response": bot_response})

if __name__ == '__main__':
    app.run(debug=True)