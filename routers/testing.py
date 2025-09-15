from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi import FastAPI, WebSocket, Depends
from fastapi.responses import HTMLResponse

# Import your new modular services
from services.extract import ExtractText, ExtractPdfs
from services.format import TextFormatter, EDRReportFormatter, ERISReportFormatter
from services.summarizer import SummarizerFactory
from services.echo import EchoServiceFactory
from services.distance import DistanceCalculatorFactory

import json
import base64
from fastapi import WebSocketDisconnect
router = APIRouter(prefix="/testing", tags=["testing"])

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Environmental Assessment Chat</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .upload-section { 
                border: 2px dashed #ccc; 
                padding: 20px; 
                margin: 20px 0; 
                text-align: center; 
                border-radius: 8px;
                background: #f9f9f9;
            }
            .report-selector {
                margin: 15px 0;
                padding: 10px;
                background: #e8f4f8;
                border-radius: 8px;
                border: 1px solid #bee5eb;
            }
            .report-selector label {
                font-weight: bold;
                margin-right: 15px;
            }
            .report-selector input[type="radio"] {
                margin: 0 5px 0 10px;
            }
            #messages { 
                border: 1px solid #ccc; 
                height: 500px; 
                overflow-y: scroll; 
                padding: 15px; 
                margin: 10px 0; 
                background: #f9f9f9; 
                border-radius: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            .message { 
                margin: 10px 0; 
                padding: 12px; 
                line-height: 1.5;
                word-wrap: break-word;
                clear: both;
                border-radius: 8px;
            }
            .user { 
                background: #e3f2fd; 
                border-left: 4px solid #2196f3;
                margin-left: 20px;
            }
            .assistant { 
                background: #f3e5f5; 
                border-left: 4px solid #9c27b0;
                margin-right: 20px;
                white-space: pre-wrap;
            }
            .system-message {
                background: #e8f5e8;
                border-left: 4px solid #4caf50;
                font-style: italic;
                color: #2e7d32;
            }
            .report-status {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                font-weight: bold;
                color: #856404;
            }
            button { 
                padding: 10px 20px; 
                margin: 5px; 
                border: none; 
                border-radius: 6px; 
                background: #2196f3; 
                color: white; 
                cursor: pointer;
                font-size: 14px;
            }
            button:hover { background: #1976d2; }
            button:disabled { 
                background: #ccc; 
                cursor: not-allowed; 
            }
            #messageText { 
                width: 70%; 
                padding: 12px; 
                border: 1px solid #ddd; 
                border-radius: 6px;
                font-size: 14px;
            }
            .section-header {
                font-weight: bold;
                color: #1976d2;
                border-bottom: 1px solid #ddd;
                padding-bottom: 5px;
                margin: 10px 0;
            }
            .status-indicator {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
            }
            .status-edr { background: #d4edda; color: #155724; }
            .status-eris { background: #cce7ff; color: #004085; }
        </style>
    </head>
    <body>
        <h1>Environmental Assessment Assistant</h1>
        
        <div class="upload-section">
            <h3>Select Report Type & Upload PDF</h3>
            
            <div class="report-selector">
                <label>Report Type:</label>
                <input type="radio" id="reportEDR" name="reportType" value="EDR" checked>
                <label for="reportEDR">EDR (Sections 5.2.1 & 5.2.2)</label>
                
                <input type="radio" id="reportERIS" name="reportType" value="ERIS">
                <label for="reportERIS">ERIS (Sections 5.2.3 & 5.2.4)</label>
            </div>
            
            <input type="file" id="fileInput" accept=".pdf" />
            <button onclick="uploadFile()">Upload PDF</button>
            <button onclick="clearSession()" style="background: #f44336;">New Session</button>
        </div>
        
        <div id='messages'></div>
        
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" placeholder="Type a message..." autocomplete="off"/>
            <button type="submit">Send</button>
        </form>
        
        <script>
            var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            var wsUrl = protocol + '//' + window.location.host + '/testing/realtest';
            var ws = new WebSocket(wsUrl);
            var currentStreamingMessage = null;
            var currentReportType = 'EDR'; // Default
            
            ws.onopen = function() {
                addMessage("Connected to Environmental Assessment Assistant", "assistant system-message");

            };
            
            ws.onmessage = function(event) {
                var text = event.data;
                
                // Check if this looks like the start of a new response
                if (text.includes("---") || text.includes("Processing") || text.includes("You:") || 
                    text.includes("Uploading:") || text.includes("Error:") || text.includes("Please") || 
                    text.includes("I have") || text.includes("Ready to") || text.includes("Using groundwater") || 
                    text.includes("Calculating") || text.includes("Generating") || text.includes("Received") || 
                    text.includes("Failed to") || text.includes("Extracted address:") || 
                    text.includes("Found EPA ECHO") || text.includes("Fetching") || 
                    text.includes("Enhanced compliance") || text.includes("Report type:")) {
                    
                    currentStreamingMessage = null;
                    
                    // Format different message types
                    if (text.includes("--- Section")) {
                        addMessage(text, "assistant section-header");
                    } else if (text.includes("Report type:") || text.includes("complete!")) {
                        addMessage(text, "assistant report-status");
                    } else {
                        addMessage(text, "assistant");
                    }
                } else {
                    // This is likely a streaming chunk, append to current message
                    if (currentStreamingMessage) {
                        appendToMessage(text);
                    } else {
                        // No current streaming message, start a new one
                        addMessage(text, "assistant");
                    }
                }
            };
            
            ws.onerror = function(error) {
                addMessage("Connection error - please refresh the page", "assistant system-message");
            };
            
            function addMessage(text, type) {
                var messages = document.getElementById('messages');
                var message = document.createElement('div');
                message.className = 'message ' + type;
                
                // Format different types of messages
                if (text.includes("Uploading:")) {
                    message.innerHTML = `<strong> ${text}</strong>`;
                } else if (text.includes("Processing")) {
                    message.innerHTML = `<strong> ${text}</strong>`;
                } else if (text.includes("Extracted address:")) {
                    message.innerHTML = `<strong> ${text}</strong>`;
                } else if (text.includes("complete!")) {
                    message.innerHTML = `<strong> ${text}</strong>`;
                } else if (text.includes("--- Section")) {
                    message.innerHTML = `<strong>${text}</strong>`;
                } else if (text.includes("Report type:")) {
                    var reportType = text.includes("EDR") ? "EDR" : "ERIS";
                    var statusClass = reportType === "EDR" ? "status-edr" : "status-eris";
                    message.innerHTML = `${text} <span class="status-indicator ${statusClass}">${reportType}</span>`;
                } else {
                    message.textContent = text;
                }
                
                messages.appendChild(message);
                messages.scrollTop = messages.scrollHeight;
                
                // If this is an assistant message, set it as the current streaming target
                if (type.includes('assistant') && !type.includes('system-message') && !type.includes('report-status')) {
                    currentStreamingMessage = message;
                }
            }
            
            function appendToMessage(text) {
                if (currentStreamingMessage) {
                    currentStreamingMessage.textContent += text;
                    var messages = document.getElementById('messages');
                    messages.scrollTop = messages.scrollHeight;
                }
            }
            
            function getCurrentReportType() {
                var radios = document.querySelectorAll('input[name="reportType"]');
                for (var radio of radios) {
                    if (radio.checked) {
                        return radio.value;
                    }
                }
                return 'EDR'; // Default fallback
            }
            
            function uploadFile() {
                var fileInput = document.getElementById('fileInput');
                var file = fileInput.files[0];
                
                if (!file) {
                    alert('Please select a PDF file');
                    return;
                }
                
                if (file.type !== 'application/pdf') {
                    alert('Please select a PDF file');
                    return;
                }
                
                currentReportType = getCurrentReportType();
                addMessage("Uploading: " + file.name, "user");
                currentStreamingMessage = null; // Reset streaming for new interaction
                
                var reader = new FileReader();
                reader.onload = function(e) {
                    var base64Data = e.target.result.split(',')[1];
                    var message = {
                        type: "file_upload",
                        filename: file.name,
                        data: base64Data,
                        reportType: currentReportType
                    };
                    ws.send(JSON.stringify(message));
                };
                reader.readAsDataURL(file);
            }
            
            function clearSession() {
                var message = { type: "clear_session" };
                ws.send(JSON.stringify(message));
                
                // Clear UI
                document.getElementById('messages').innerHTML = '';
                document.getElementById('messageText').value = '';
                
                // Reset to default
                document.getElementById('reportEDR').checked = true;
                currentReportType = 'EDR';
                
                // Re-add welcome message
                setTimeout(() => {
                    addMessage("Session cleared. Select your report type and upload a new PDF document.", "assistant system-message");
                }, 100);
            }
            
            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value.trim() === '') return;
                
                var message = {
                    type: "chat",
                    content: input.value,
                    reportType: currentReportType
                };
                
                addMessage("You: " + input.value, "user");
                currentStreamingMessage = null; // Reset streaming for new interaction
                ws.send(JSON.stringify(message));
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

# Dependency functions using your new modular services
async def get_text_extractor():
    return ExtractPdfs(layout_mode=True)

async def get_edr_formatter():
    return EDRReportFormatter()

async def get_eris_formatter():
    return ERISReportFormatter()

async def get_distance_calculator():
    return DistanceCalculatorFactory.create_calculator("precisely")

@router.get("/")
async def get():
    return HTMLResponse(html)

@router.websocket("/realtest")
async def websocket_endpoint(
    websocket: WebSocket,
    extractor: ExtractText = Depends(get_text_extractor),
    edr_formatter: TextFormatter = Depends(get_edr_formatter),
    eris_formatter: TextFormatter = Depends(get_eris_formatter),
    distance_calculator = Depends(get_distance_calculator)
):
    await websocket.accept()
    
    session = {
        "report_type": None,
        "main_document": None,
        "surrounding_documents": [],
        "subject_address": None,
        "section_content": None,
        "workflow_stage": "awaiting_report_selection"
    }
    
    await websocket.send_text("Hello! Select your report type (EDR or ERIS) and upload a PDF document to begin.")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "file_upload":
                    await process_pdf(websocket, message, session, extractor, edr_formatter, eris_formatter)
                elif message_type == "chat":
                    await handle_intelligent_chat(websocket, message, session, distance_calculator)
                elif message_type == "clear_session":
                    await clear_session(websocket, session)
                    
            except json.JSONDecodeError:
                await websocket.send_text("Please upload a PDF or use the chat interface.")
                
    except WebSocketDisconnect:
        pass

async def clear_session(websocket, session):
    """Clear the current session and reset to initial state"""
    session.clear()
    session.update({
        "report_type": None,
        "main_document": None,
        "surrounding_documents": [],
        "subject_address": None,
        "section_content": None,
        "workflow_stage": "awaiting_report_selection"
    })
    await websocket.send_text("Session cleared successfully.")

async def process_pdf(websocket, message, session, extractor, edr_formatter, eris_formatter):
    report_type = message.get("reportType", "EDR")
    session["report_type"] = report_type
    
    await websocket.send_text(f"Report type: {report_type}")
    await websocket.send_text("Processing PDF...")
    
    try:
        pdf_bytes = base64.b64decode(message["data"])
        filename = message["filename"]
        
        # Extract text using modular extractor
        extraction_result = extractor.extract(pdf_bytes, filename)
        raw_text = extraction_result.get("text", "").strip()
        
        if not raw_text:
            await websocket.send_text("Could not extract text from PDF")
            return
        
        # Get appropriate ECHO service and formatter based on report type
        echo_service = EchoServiceFactory.create_service(report_type)
        formatter = edr_formatter if report_type == "EDR" else eris_formatter
        
        # Check for ECHO URLs and process if found
        echo_summary = None
        try:
            echo_summary = echo_service.get_compliance_summary(raw_text)
            if echo_summary:
                await websocket.send_text(f"Found EPA ECHO data - fetching enhanced compliance information...")
                await websocket.send_text("Enhanced compliance data retrieved successfully.")
        except Exception as e:
            await websocket.send_text(f"Note: Could not retrieve ECHO data: {str(e)}")
        
        # Format text using appropriate formatter
        formatted = formatter.format(raw_text)
        
        # Check if this is main document or surrounding property
        if not session.get("main_document"):
            # This is the main property document
            await websocket.send_text("Processing main property document...")
            
            # Generate appropriate section based on report type
            section_number = "5.2.1" if report_type == "EDR" else "5.2.3"
            await websocket.send_text(f"--- Section {section_number} ---")
            
            # Get appropriate summarizer
            summarizer = SummarizerFactory.get_summarizer(report_type, section_number)
            
            if echo_summary:
                # Enhanced context with ECHO data
                enhanced_context = f"""Environmental Database Document Content:
{formatted}

Enhanced EPA ECHO Compliance Summary:
{echo_summary}

Instructions: Generate Section {section_number} incorporating both the environmental database information and the enhanced EPA ECHO compliance summary. When the document mentions ECHO database listings, enhance those entries with the detailed compliance information provided above. Integrate the ECHO compliance data seamlessly into the facility summary to provide comprehensive environmental assessment information."""
                
                result = await summarizer.generate_section_streaming(
                    websocket,
                    enhanced_context
                )
            else:
                # Standard section without ECHO enhancement
                result = await summarizer.generate_section_streaming(
                    websocket,
                    formatted
                )
            
            session["main_document"] = {
                "filename": filename,
                "text": raw_text,
                "formatted": formatted,
                "echo_summary": echo_summary
            }
            
            # Handle different return formats from different summarizers
            if isinstance(result, dict):
                session["section_content"] = result.get("section_content")
                session["subject_address"] = result.get("subject_address")
            else:
                session["section_content"] = result
            
            session["workflow_stage"] = "can_upload_surrounding"
            
            await websocket.send_text(f"Section {section_number} complete!")
            
            next_section = "5.2.2" if report_type == "EDR" else "5.2.4"
            await websocket.send_text(f"You can now upload surrounding properties PDFs to enable Section {next_section} generation.")
            
        else:
            # This is a surrounding property document
            await websocket.send_text(f"Processing surrounding property document: {filename}")
            
            surrounding_doc = {
                "filename": filename,
                "text": raw_text,
                "formatted": formatted,
                "echo_summary": echo_summary
            }
            session["surrounding_documents"].append(surrounding_doc)
            
            next_section = "5.2.2" if report_type == "EDR" else "5.2.4"
            await websocket.send_text(f"Surrounding property '{filename}' processed. Total surrounding documents: {len(session['surrounding_documents'])}")
            await websocket.send_text(f"You can upload more surrounding properties or ask me to generate Section {next_section}.")
        
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")

def extract_groundwater_direction(text):
    """Extract groundwater flow direction from user message"""
    text_lower = text.lower()
    
    direction_patterns = {
        'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W',
        'northeast': 'NE', 'northwest': 'NW', 'southeast': 'SE', 'southwest': 'SW',
        'ne': 'NE', 'nw': 'NW', 'se': 'SE', 'sw': 'SW',
        'n ': 'N', 'e ': 'E', 's ': 'S', 'w ': 'W'
    }
    
    for pattern, direction in direction_patterns.items():
        if pattern in text_lower:
            return direction
    
    return None

async def handle_intelligent_chat(websocket, message, session, distance_calculator):
    user_question = message.get("content", "").strip()
    report_type = session.get("report_type", "EDR")
    
    if not session.get("main_document"):
        await websocket.send_text("Please upload the subject propety adress and pdf file for the subject property.")
        return
    
    # Determine section numbers based on report type
    surrounding_section = "5.2.2" if report_type == "EDR" else "5.2.4"
    
    # Check if user wants the surrounding properties section
    section_triggers = [surrounding_section, surrounding_section.replace(".", ""), "surrounding properties"]
    if report_type == "EDR":
        section_triggers.extend(["generate 5.2.2", "section 5.2.2"])
    else:
        section_triggers.extend(["generate 5.2.4", "section 5.2.4"])
    
    if any(phrase in user_question.lower() for phrase in section_triggers):
        
        # Enforce sequential workflow - prevent jumping to surrounding section without completing main section
        if not session.get("section_content"):
            await websocket.send_text("Please complete the subject property section first before proceeding to surrounding properties.")
            return
        
        if not session.get("subject_address"):
            await websocket.send_text("I need the subject property address first. The main document didn't contain extractable address information.")
            return
        
        if not session.get("surrounding_documents"):
            await websocket.send_text(f"I can generate Section {surrounding_section} for {session['subject_address']}, but I need surrounding properties data first.")
            await websocket.send_text(f"Please upload PDFs containing surrounding property database listings, then ask me to generate Section {surrounding_section} again.")
            return
        
        # Check if we have surrounding addresses
        if not session.get("surrounding_addresses"):
            await websocket.send_text(f"I have {len(session['surrounding_documents'])} surrounding property document(s), but I need the addresses for distance calculations.")
            await websocket.send_text("Please provide the addresses of the surrounding properties (one per message or comma-separated).")
            session["awaiting_addresses"] = True
            return
        
        # Both main and surrounding data available
        await websocket.send_text(f"Ready to generate Section {surrounding_section} for {session['subject_address']}")
        await websocket.send_text(f"I have {len(session['surrounding_documents'])} surrounding property document(s)")
        await websocket.send_text("I need the groundwater flow direction (like 'northeast', 'SW', 'north', etc.)")
        session["awaiting_groundwater"] = True
        return
    
    # Handle address collection
    if session.get("awaiting_addresses"):
        addresses = [addr.strip() for addr in user_question.split(',')]
        addresses = [addr for addr in addresses if addr and len(addr) > 10]
        
        if addresses:
            session["surrounding_addresses"] = addresses
            session["awaiting_addresses"] = False
            await websocket.send_text(f"Received {len(addresses)} surrounding property addresses:")
            for addr in addresses:
                await websocket.send_text(f"  - {addr}")
            await websocket.send_text("Now I need the groundwater flow direction (like 'northeast', 'SW', 'north', etc.)")
            session["awaiting_groundwater"] = True
        else:
            await websocket.send_text("Please provide valid addresses. Example: '123 Main St, City, State' or provide multiple addresses separated by commas.")
        return
    
    # Handle groundwater direction and generate surrounding section
    if session.get("awaiting_groundwater"):
        groundwater_direction = extract_groundwater_direction(user_question)
        if groundwater_direction:
            await websocket.send_text(f"Using groundwater flow direction: {groundwater_direction}")
            await websocket.send_text("Calculating distances...")
            
            try:
                # Calculate distances using modular distance calculator
                distance_data = distance_calculator.calculate_distances(
                    session["subject_address"], 
                    session["surrounding_addresses"]
                )
                
                await websocket.send_text(f"Calculated distances for {len(distance_data['distances'])} properties")
                
                if distance_data.get('failed'):
                    await websocket.send_text(f"Failed to calculate distances for: {distance_data['failed']}")
                
                # Combine surrounding property data with ECHO enhancement
                combined_surrounding_data = ""
                combined_echo_summaries = ""
                
                for doc in session["surrounding_documents"]:
                    combined_surrounding_data += f"\n--- {doc['filename']} ---\n{doc['formatted']}\n"
                    
                    if doc.get('echo_summary'):
                        combined_echo_summaries += f"\n--- ECHO Compliance Data for {doc['filename']} ---\n{doc['echo_summary']}\n"
                
                surrounding_section = "5.2.2" if report_type == "EDR" else "5.2.4"
                await websocket.send_text(f"Generating Section {surrounding_section}...")
                await websocket.send_text(f"--- Section {surrounding_section} ---")
                
                # Get appropriate summarizer for surrounding section
                summarizer = SummarizerFactory.get_summarizer(report_type, surrounding_section)
                
                if combined_echo_summaries.strip():
                    enhanced_context = f"""Surrounding Properties Environmental Database Data:
{combined_surrounding_data}

Enhanced EPA ECHO Compliance Summaries for Surrounding Properties:
{combined_echo_summaries}

Instructions: Generate Section {surrounding_section} incorporating both the environmental database information and the enhanced EPA ECHO compliance summaries. When properties are mentioned as having ECHO database listings, enhance those entries with the detailed compliance information provided above."""
                    
                    result = await summarizer.generate_section_streaming(
                        websocket,
                        enhanced_context,
                        subject_address=session["subject_address"],
                        groundwater_flow=groundwater_direction,
                        distance_data=distance_data
                    )
                else:
                    result = await summarizer.generate_section_streaming(
                        websocket,
                        combined_surrounding_data,
                        subject_address=session["subject_address"],
                        groundwater_flow=groundwater_direction,
                        distance_data=distance_data
                    )
                
                session["surrounding_section"] = result
                session["awaiting_groundwater"] = False
                
                await websocket.send_text(f"Section {surrounding_section} complete!")
                
            except Exception as e:
                await websocket.send_text(f"Error generating Section {surrounding_section}: {str(e)}")
                session["awaiting_groundwater"] = False
        else:
            await websocket.send_text("I didn't recognize a groundwater flow direction. Please specify like: 'northeast', 'SW', 'north', 'southeast', etc.")
        return
    
    # General Q&A using intelligent chat
    all_documents_context = f"Main Document ({session['main_document']['filename']}):\n{session['main_document']['formatted'][:2000]}"
    
    if session.get("surrounding_documents"):
        all_documents_context += "\n\nSurrounding Properties Documents:\n"
        for doc in session["surrounding_documents"]:
            all_documents_context += f"\n{doc['filename']}:\n{doc['formatted'][:1000]}"
    
    echo_context = ""
    if session.get("main_document", {}).get("echo_summary"):
        echo_context += f"\n\nEnhanced ECHO Compliance Data for Main Property:\n{session['main_document']['echo_summary']}"
    
    for doc in session.get("surrounding_documents", []):
        if doc.get("echo_summary"):
            echo_context += f"\n\nEnhanced ECHO Compliance Data for {doc['filename']}:\n{doc['echo_summary']}"
    
    context = f"""
    You are an environmental assessment assistant working with {report_type} reports. A user has uploaded and processed PDF documents.
    
    {all_documents_context}
    
    {echo_context}
    
    Generated Section Content:
    {session.get("section_content", "Not yet generated")}
    
    Subject Property Address: {session.get("subject_address", "Not extracted")}
    
    Report Type: {report_type}
    
    User Question: {user_question}
    
    Please answer the user's question based on this environmental assessment information. Be specific and reference the actual data from the documents.
    """
    
    try:
        # Use intelligent chat from factory
        chat_summarizer = SummarizerFactory.get_summarizer("", "chat")
        await chat_summarizer.generate_section_streaming(
            websocket,
            context,
            temperature=0.1,
            max_tokens=800
        )
        
    except Exception as e:
        await websocket.send_text(f"I had trouble processing your question: {str(e)}")