import streamlit as st
import PyPDF2
from PIL import Image
import pytesseract
import cohere
import os
from dotenv import load_dotenv
from fpdf import FPDF
load_dotenv()

# Load Cohere API
co = cohere.Client(os.getenv("COHERE_API_KEY"))

st.set_page_config(page_title="Insurance Claim Assistant (Multi-Agent)", layout="centered")
st.title("Smart Insurance Assistant")

# Initialize user input cache
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}

# --------------- Upload Section ---------------
st.header("Upload Your Claim Document")
uploaded_file = st.file_uploader("Upload a PDF or image", type=["pdf", "png", "jpg", "jpeg"])
extracted_text = ""
doc_type_result = ""

if uploaded_file:
    if uploaded_file.type == "application/pdf":
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
        except Exception as e:
            st.error(f"PDF extraction failed: {e}")
    else:
        try:
            image = Image.open(uploaded_file)
            extracted_text = pytesseract.image_to_string(image)
        except Exception as e:
            st.error(f"OCR failed: {e}")

    if extracted_text:
        st.success("✅ Text extracted from the document.")
        st.text_area("🧾 Extracted Text", extracted_text, height=200)
        with st.spinner("🔍 Classifying document type..."):
            prompt = f"Classify the type of this document based on its content. Choose from: Hospital Bill, Discharge Summary, Doctor's Report, Police Report, Vehicle Image, Medical Report, Flight Ticket, Passport Copy, Lost Baggage Report.\n\nDocument Text:\n{extracted_text}"
            try:
                response = co.generate(model="command", prompt=prompt, max_tokens=400)
                doc_type_result = response.generations[0].text.strip()
                st.info(f"🗂️ Detected Document Type: **{doc_type_result}**")
            except Exception as e:
                st.error(f"❌ Classification failed: {e}")

# --------------- Claim Form Section ---------------
st.header("📝 Claim Details")
claim_type = st.selectbox("Select Claim Type", ["Health", "Accident", "Travel"])
user_description = st.text_area("Briefly describe what happened")

st.session_state.user_inputs["claim_type"] = claim_type
st.session_state.user_inputs["user_description"] = user_description
st.session_state.user_inputs["extracted_text"] = extracted_text

if claim_type:
    required_docs = {
        "Health": ["Hospital Bill", "Discharge Summary", "Doctor's Report"],
        "Accident": ["Police Report", "Vehicle Images", "Medical Report"],
        "Travel": ["Flight Ticket", "Passport Copy", "Lost Baggage Report"]
    }
    checklist = required_docs[claim_type]
    st.markdown("#### 📌 Required Documents:")
    if doc_type_result:
        missing_docs = [doc for doc in checklist if doc.lower() not in doc_type_result.lower()]
        if missing_docs:
            st.warning("⚠️ Missing document(s): " + ", ".join(missing_docs))
        else:
            st.success("✅ All required documents appear to be present.")

# --------------- Guided Claim Writer ---------------
with st.expander("🧠 Need help writing the incident description?"):
    claim_type = st.session_state.get("claim_type", "Health")

    col1, col2 = st.columns(2)
    with col1:
        policy_number = st.text_input("Policy Number")
        incident_date = st.date_input("Date of Incident")
        location = st.text_input("Location")
        persons_involved = st.text_input("People Involved")
        contact_email = st.text_input("Your Email")
        contact_phone = st.text_input("Your Phone Number")
    with col2:
        result = st.text_area("What was the result or damage?")
        estimated_expenses = st.text_input("Estimated Claim Amount (INR)")
        address = st.text_area("Your Address")

        # 🎯 Dynamic input fields based on claim type
        extra_details = ""
        if claim_type == "Health":
            hospital = st.text_input("Hospital Name")
            treatment = st.text_area("Treatment Received")
            if hospital or treatment:
                extra_details += f"Hospital: {hospital}\nTreatment: {treatment}"
        elif claim_type == "Accident":
            vehicle_type = st.text_input("Vehicle Type (e.g., scooter, car)")
            police_report = st.text_area("Police Report Summary")
            if vehicle_type or police_report:
                extra_details += f"Vehicle: {vehicle_type}\nPolice Report: {police_report}"
        elif claim_type == "Travel":
            trip_details = st.text_input("Trip Details (flight, destination, etc.)")
            loss_description = st.text_area("Loss or Incident Description")
            if trip_details or loss_description:
                extra_details += f"Trip Info: {trip_details}\nIncident: {loss_description}"

    # Update session state
    st.session_state.user_inputs.update({
        "policy_number": policy_number,
        "incident_date": str(incident_date),
        "location": location,
        "persons_involved": persons_involved,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "result": result,
        "estimated_expenses": estimated_expenses,
        "address": address,
        "extra_details": extra_details
    })

    if st.button("✍️ Help me write the description letter"):
        # Filter only non-empty fields
        fields = {
            "Policy Number": policy_number,
            "Claim Type": claim_type,
            "Incident Date": incident_date,
            "Location": location,
            "People Involved": persons_involved,
            "Result": result,
            "Estimated Claim (INR)": estimated_expenses,
            "Contact Email": contact_email,
            "Phone": contact_phone,
            "Address": address,
            "Additional Details": extra_details
        }

        # Generate prompt from non-empty inputs
        prompt_body = "\n".join([f"{key}: {value}" for key, value in fields.items() if value])
        prompt = f"""
Write a formal insurance claim letter using the following details. Only include what is given:

{prompt_body}

The tone should be polite, formal, and easy to understand.
"""

        try:
            response = co.generate(model="command", prompt=prompt, max_tokens=800)
            user_description = response.generations[0].text.strip()
            st.session_state.user_inputs["user_description"] = user_description
            st.session_state["user_description"] = user_description  # <-- add this line
            st.success("✅ Description generated:")
            st.text_area("Generated Description", user_description, height=300)
        except Exception as e:
            st.error(f"❌ Failed to generate description: {e}")

from fpdf import FPDF
import smtplib

from io import BytesIO
from fpdf import FPDF


# PDF Download
if "user_description" in st.session_state and st.session_state["user_description"]:
    user_description = st.session_state["user_description"]

    if st.button("📄 Download Claim Letter as PDF"):
        try:
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            # Handle characters not supported by FPDF
            safe_text = user_description.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 10, safe_text)

            # Write PDF to a string and then to memory
            pdf_output = pdf.output(dest='S').encode('latin-1')
            pdf_bytes = BytesIO(pdf_output)

            st.download_button(
                label="⬇️ Click to Download PDF",
                data=pdf_bytes,
                file_name="claim_letter.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"❌ Failed to create PDF: {e}")

# --------------- Claim Estimator ---------------
if st.button("💰 Estimate Claim Amount"):
    prompt = f"""
You are an experienced insurance claim analyst. Based on the following claim details, provide an estimated insurance payout in INR along with a brief justification.

Use average Indian auto repair costs and similar real-world cases to inform your estimate. Be reasonable and avoid exaggeration.

---

Claim Type: {claim_type}
Incident Location: {location}
Date: {incident_date}
People Involved: {persons_involved}
Claimant Contact: {contact_email}, {contact_phone}
Damage Summary: {result}
Estimated by User: {estimated_expenses}
Extracted Document Content: {extracted_text}

---

Respond in the following format:

1. Estimated Amount (INR): ₹_____
2. Reason for Estimate: ___
"""
    try:
        response = co.generate(model="command", prompt=prompt, max_tokens=600)
        result = response.generations[0].text.strip()
        st.markdown("### 💸 Estimated Claim Amount")
        st.text_area("Estimate & Justification", result, height=280)
    except Exception as e:
        st.error(f"❌ Estimation failed: {e}")

# --------------- Chatbot Section ---------------
st.header("💬 Ask Our Insurance Bot")

# Initialize chat history if not present
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Ask a claim-related question...")

if user_input:
    # Add user message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Compile context from user inputs (non-empty only)
    context_info = "\n".join(
        [f"{key.replace('_',' ').capitalize()}: {value}" 
         for key, value in st.session_state.user_inputs.items() if value]
    )

    # Generate assistant response using Cohere
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = co.generate(
                    model="command",
                    prompt=(
                        "You are a helpful insurance assistant. Use the user's previous inputs if helpful.\n\n"
                        f"User Inputs:\n{context_info}\n\n"
                        f"Question:\n{user_input}"
                    ),
                    max_tokens=800,
                    temperature=0.5
                )
                reply = response.generations[0].text.strip()
            except Exception as e:
                reply = f"❌ Sorry, there was an error: {e}"
            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
