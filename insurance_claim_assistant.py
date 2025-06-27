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
                response = co.generate(model="command", prompt=prompt, max_tokens=50)
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
    col1, col2 = st.columns(2)
    with col1:
        incident_date = st.date_input("Date of Incident")
        location = st.text_input("Location")
        persons_involved = st.text_input("People Involved")
        contact_email = st.text_input("Your Email")
        contact_phone = st.text_input("Your Phone Number")
    with col2:
        result = st.text_area("What was the result or damage?")
        estimated_expenses = st.text_input("Estimated Claim Amount (INR)")
        address = st.text_area("Your Address")

    st.session_state.user_inputs.update({
        "incident_date": str(incident_date),
        "location": location,
        "persons_involved": persons_involved,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "result": result,
        "estimated_expenses": estimated_expenses,
        "address": address
    })

    if st.button("✍️ Help me write the description"):
        prompt = f"""
Write a formal insurance claim letter using the following details:\n
Incident Date: {incident_date}\nLocation: {location}\nPeople Involved: {persons_involved}\nResult: {result}\nClaim Type: {claim_type}\nEstimated Claim: {estimated_expenses} INR\nContact Email: {contact_email}\nContact Phone: {contact_phone}\nAddress: {address}
"""
        try:
            response = co.generate(model="command", prompt=prompt, max_tokens=400)
            user_description = response.generations[0].text.strip()
            st.session_state.user_inputs["user_description"] = user_description
            st.success("✅ Description generated:")
            st.text_area("Generated Description", user_description, height=300)
        except Exception as e:
            st.error(f"❌ Failed to generate description: {e}")

# --------------- Fraud Checker ---------------
if st.button("🚨 Check for Red Flags"):
    prompt = f"Check for suspicious indicators in the following document:\n{extracted_text}"
    try:
        response = co.generate(model="command", prompt=prompt, max_tokens=120)
        result = response.generations[0].text.strip()
        st.warning(result)
    except Exception as e:
        st.error(f"❌ Red flag check failed: {e}")

# --------------- Claim Estimator ---------------
if st.button("💰 Estimate Claim Amount"):
    prompt = f"""
Estimate a reasonable insurance claim amount in INR based on this claim:

Claim Type: {claim_type}
Description: {user_description}
Document: {extracted_text}
"""
    try:
        response = co.generate(model="command", prompt=prompt, max_tokens=300)
        result = response.generations[0].text.strip()
        st.text_area("💸 Estimated Claim Amount", result, height=250)
    except Exception as e:
        st.error(f"❌ Estimation failed: {e}")

# --------------- Chatbot Section ---------------
st.header("💬 Ask Our Insurance Bot")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask a claim-related question...")
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Compile full context from user inputs
    context_info = "\n".join([f"{key.replace('_',' ').capitalize()}: {value}" for key, value in st.session_state.user_inputs.items() if value])

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = co.generate(
                model="command",
                prompt=f"You are a helpful insurance assistant. Use the user's previous inputs if helpful.\n\nUser Inputs:\n{context_info}\n\nQuestion:\n{user_input}",
                max_tokens=300,
                temperature=0.5
            )
            reply = response.generations[0].text.strip()
            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})