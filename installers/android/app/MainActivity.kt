/**
 * ArciTEK.AI Android - Main Activity
 * "Every build is a work of art" - infinite♾2025
 * 
 * Main entry point for the ArciTEK.AI mobile companion app.
 * Provides setup wizard, dashboard, and remote management.
 */

package com.infinite2025.arcitek.ai.ui

import android.content.Intent
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebChromeClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setContent {
            ArciTEKTheme {
                ArciTEKApp()
            }
        }
    }
}

@Composable
fun ArciTEKTheme(content: @Composable () -> Unit) {
    val darkColorScheme = darkColorScheme(
        primary = Color(0xFF4A9EFF),
        secondary = Color(0xFF7C4DFF),
        background = Color(0xFF1A1A2E),
        surface = Color(0xFF16213E),
        onPrimary = Color.White,
        onSecondary = Color.White,
        onBackground = Color.White,
        onSurface = Color.White
    )
    
    MaterialTheme(
        colorScheme = darkColorScheme,
        content = content
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArciTEKApp() {
    var currentScreen by remember { mutableStateOf("splash") }
    var isSetupComplete by remember { mutableStateOf(false) }
    var serverUrl by remember { mutableStateOf("http://localhost:8000") }
    
    when (currentScreen) {
        "splash" -> SplashScreen { currentScreen = if (isSetupComplete) "dashboard" else "setup" }
        "setup" -> SetupWizard(
            onComplete = { url ->
                serverUrl = url
                isSetupComplete = true
                currentScreen = "dashboard"
            }
        )
        "dashboard" -> DashboardScreen(serverUrl)
    }
}

@Composable
fun SplashScreen(onComplete: () -> Unit) {
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(2000)
        onComplete()
    }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFF1A1A2E), Color(0xFF16213E), Color(0xFF0F3460))
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "ArciTEK.AI",
                fontSize = 42.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF4A9EFF)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Quantum-Enhanced AI Development Platform",
                fontSize = 14.sp,
                color = Color.White.copy(alpha = 0.7f)
            )
            Spacer(modifier = Modifier.height(32.dp))
            CircularProgressIndicator(
                color = Color(0xFF4A9EFF),
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.height(48.dp))
            Text(
                text = "\"Every build is a work of art\"",
                fontSize = 12.sp,
                color = Color.White.copy(alpha = 0.5f),
                fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
            )
            Text(
                text = "infinite♾2025",
                fontSize = 12.sp,
                color = Color(0xFF4A9EFF).copy(alpha = 0.7f)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupWizard(onComplete: (String) -> Unit) {
    var currentStep by remember { mutableIntStateOf(0) }
    var serverUrl by remember { mutableStateOf("") }
    var apiKey by remember { mutableStateOf("") }
    var autoConnect by remember { mutableStateOf(true) }
    
    val steps = listOf("Welcome", "Connect", "API Keys", "Complete")
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ArciTEK.AI Setup") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF16213E)
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF1A1A2E))
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Progress indicator
            LinearProgressIndicator(
                progress = { (currentStep + 1f) / steps.size },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(2.dp)),
                color = Color(0xFF4A9EFF)
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "Step ${currentStep + 1} of ${steps.size}: ${steps[currentStep]}",
                fontSize = 12.sp,
                color = Color.White.copy(alpha = 0.6f)
            )
            
            Spacer(modifier = Modifier.height(32.dp))
            
            // Step content
            when (currentStep) {
                0 -> WelcomeStep()
                1 -> ConnectStep(
                    serverUrl = serverUrl,
                    onUrlChange = { serverUrl = it },
                    autoConnect = autoConnect,
                    onAutoConnectChange = { autoConnect = it }
                )
                2 -> ApiKeyStep(
                    apiKey = apiKey,
                    onApiKeyChange = { apiKey = it }
                )
                3 -> CompleteStep()
            }
            
            Spacer(modifier = Modifier.weight(1f))
            
            // Navigation buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                if (currentStep > 0) {
                    OutlinedButton(onClick = { currentStep-- }) {
                        Text("Back")
                    }
                } else {
                    Spacer(modifier = Modifier.width(1.dp))
                }
                
                Button(
                    onClick = {
                        if (currentStep < steps.size - 1) {
                            currentStep++
                        } else {
                            onComplete(serverUrl.ifEmpty { "http://localhost:8000" })
                        }
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF4A9EFF)
                    )
                ) {
                    Text(if (currentStep < steps.size - 1) "Next" else "Get Started")
                }
            }
        }
    }
}

@Composable
fun WelcomeStep() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(
            imageVector = Icons.Default.Rocket,
            contentDescription = null,
            modifier = Modifier.size(80.dp),
            tint = Color(0xFF4A9EFF)
        )
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            text = "Welcome to ArciTEK.AI",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "This mobile companion connects to your ArciTEK.AI server, " +
                   "giving you access to quantum computing, AI models, and " +
                   "development tools from anywhere.",
            fontSize = 14.sp,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(24.dp))
        
        // Feature cards
        FeatureCard("5 Quantum Platforms", "IBM, IonQ, Google, Braket, Azure")
        FeatureCard("325B AI Parameters", "SupersynapAI, Argo, Chimera")
        FeatureCard("99.97% Precision", "Quantum Perfect builds")
    }
}

@Composable
fun FeatureCard(title: String, subtitle: String) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF16213E))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = null,
                tint = Color(0xFF4A9EFF),
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(text = title, fontWeight = FontWeight.Medium, color = Color.White)
                Text(text = subtitle, fontSize = 12.sp, color = Color.White.copy(alpha = 0.6f))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConnectStep(
    serverUrl: String,
    onUrlChange: (String) -> Unit,
    autoConnect: Boolean,
    onAutoConnectChange: (Boolean) -> Unit
) {
    Column {
        Text(
            text = "Connect to Server",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Enter the URL of your ArciTEK.AI server:",
            color = Color.White.copy(alpha = 0.7f)
        )
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = serverUrl,
            onValueChange = onUrlChange,
            label = { Text("Server URL") },
            placeholder = { Text("http://localhost:8000") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(
                checked = autoConnect,
                onCheckedChange = onAutoConnectChange
            )
            Text(
                text = "Auto-connect on startup",
                color = Color.White.copy(alpha = 0.7f)
            )
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF16213E))
        ) {
            Text(
                text = "Tip: If running ArciTEK.AI on the same network, " +
                       "use your computer's IP address (e.g., http://192.168.1.100:8000)",
                modifier = Modifier.padding(12.dp),
                fontSize = 12.sp,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApiKeyStep(apiKey: String, onApiKeyChange: (String) -> Unit) {
    Column {
        Text(
            text = "API Configuration",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Optionally configure API keys for direct mobile access:",
            color = Color.White.copy(alpha = 0.7f)
        )
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = apiKey,
            onValueChange = onApiKeyChange,
            label = { Text("OpenAI API Key (optional)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF16213E))
        ) {
            Text(
                text = "You can skip this step and configure API keys later " +
                       "through the server's configuration wizard.",
                modifier = Modifier.padding(12.dp),
                fontSize = 12.sp,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
    }
}

@Composable
fun CompleteStep() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(
            imageVector = Icons.Default.CheckCircle,
            contentDescription = null,
            modifier = Modifier.size(80.dp),
            tint = Color(0xFF4CAF50)
        )
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            text = "Setup Complete!",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "ArciTEK.AI is ready to use. Tap 'Get Started' to open the dashboard.",
            fontSize = 14.sp,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(serverUrl: String) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ArciTEK.AI") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF16213E)
                ),
                actions = {
                    IconButton(onClick = { /* Refresh */ }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = { /* Settings */ }) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        AndroidView(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            factory = { context ->
                WebView(context).apply {
                    webViewClient = WebViewClient()
                    webChromeClient = WebChromeClient()
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.loadWithOverviewMode = true
                    settings.useWideViewPort = true
                    loadUrl(serverUrl)
                }
            }
        )
    }
}
