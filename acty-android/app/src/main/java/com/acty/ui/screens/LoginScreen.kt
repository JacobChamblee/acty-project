package com.acty.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.acty.data.AuthManager
import com.acty.data.AuthResult
import com.acty.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    onLoginSuccess:       () -> Unit,
    onNavigateToRegister: () -> Unit,
) {
    val context      = LocalContext.current
    val auth         = remember { AuthManager(context) }
    val scope        = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    var email          by remember { mutableStateOf("") }
    var password       by remember { mutableStateOf("") }
    var pwVisible      by remember { mutableStateOf(false) }
    var loading        by remember { mutableStateOf(false) }
    var errorMessage   by remember { mutableStateOf("") }

    fun doLogin() {
        if (email.isBlank() || password.isBlank()) { errorMessage = "Please fill in all fields."; return }
        focusManager.clearFocus()
        scope.launch {
            loading = true; errorMessage = ""
            delay(300L)
            when (val r = auth.login(email.trim(), password)) {
                is AuthResult.Success -> onLoginSuccess()
                is AuthResult.Error   -> { errorMessage = r.message; loading = false }
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFFF0F4FF), Color(0xFFF8FAFC)),
                    startY = 0f, endY = 900f,
                )
            )
            .systemBarsPadding(),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(72.dp))

            // ── Brand ──────────────────────────────────────────
            Text("🌵", fontSize = 52.sp, textAlign = TextAlign.Center)
            Spacer(Modifier.height(10.dp))
            Text(
                "Cactus Insights",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.ExtraBold,
                    color      = CactusBlue,
                ),
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Sign in to your account",
                style = MaterialTheme.typography.bodyMedium.copy(color = TextDim),
            )
            Spacer(Modifier.height(40.dp))

            // ── Form card ──────────────────────────────────────
            Surface(
                shape     = RoundedCornerShape(20.dp),
                color     = Color.White,
                shadowElevation = 4.dp,
                modifier  = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(24.dp)) {

                    // Error banner
                    if (errorMessage.isNotEmpty()) {
                        Surface(
                            shape  = RoundedCornerShape(10.dp),
                            color  = StatusRedBg,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                errorMessage,
                                style    = MaterialTheme.typography.bodySmall.copy(color = StatusRed),
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                            )
                        }
                        Spacer(Modifier.height(16.dp))
                    }

                    // Email
                    AuthField(
                        value         = email,
                        onValueChange = { email = it; errorMessage = "" },
                        label         = "Email",
                        keyboardType  = KeyboardType.Email,
                        imeAction     = ImeAction.Next,
                        onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                    )
                    Spacer(Modifier.height(12.dp))

                    // Password
                    AuthField(
                        value                = password,
                        onValueChange        = { password = it; errorMessage = "" },
                        label                = "Password",
                        keyboardType         = KeyboardType.Password,
                        imeAction            = ImeAction.Done,
                        onDone               = { doLogin() },
                        visualTransformation = if (pwVisible) VisualTransformation.None
                                               else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { pwVisible = !pwVisible }) {
                                Icon(
                                    if (pwVisible) Icons.Filled.Visibility
                                    else           Icons.Filled.VisibilityOff,
                                    contentDescription = "Toggle password",
                                    tint = TextDim,
                                )
                            }
                        },
                    )
                    Spacer(Modifier.height(24.dp))

                    // Sign In button
                    Button(
                        onClick  = { doLogin() },
                        enabled  = !loading,
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                        shape    = RoundedCornerShape(13.dp),
                        colors   = ButtonDefaults.buttonColors(containerColor = CactusBlue),
                    ) {
                        if (loading) {
                            CircularProgressIndicator(
                                color       = Color.White,
                                modifier    = Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Text("Sign In", fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                        }
                    }
                }
            }

            Spacer(Modifier.height(22.dp))

            // Register link
            Row(
                horizontalArrangement = Arrangement.Center,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Text(
                    "Don't have an account?",
                    style = MaterialTheme.typography.bodyMedium.copy(color = TextDim),
                )
                TextButton(onClick = onNavigateToRegister) {
                    Text("Create one free", color = CactusBlue, fontWeight = FontWeight.SemiBold)
                }
            }
            Spacer(Modifier.height(48.dp))
        }
    }
}

// ── Shared auth text field ────────────────────────────────────────────────────

@Composable
fun AuthField(
    value:                String,
    onValueChange:        (String) -> Unit,
    label:                String,
    keyboardType:         KeyboardType          = KeyboardType.Text,
    imeAction:            ImeAction             = ImeAction.Next,
    onNext:               () -> Unit            = {},
    onDone:               () -> Unit            = {},
    visualTransformation: VisualTransformation  = VisualTransformation.None,
    trailingIcon:         @Composable (() -> Unit)? = null,
) {
    OutlinedTextField(
        value         = value,
        onValueChange = onValueChange,
        label         = { Text(label) },
        singleLine    = true,
        modifier      = Modifier.fillMaxWidth(),
        shape         = RoundedCornerShape(12.dp),
        keyboardOptions = KeyboardOptions(
            keyboardType = keyboardType,
            imeAction    = imeAction,
        ),
        keyboardActions = KeyboardActions(
            onNext = { onNext() },
            onDone = { onDone() },
        ),
        visualTransformation = visualTransformation,
        trailingIcon         = trailingIcon,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor   = CactusBlue,
            focusedLabelColor    = CactusBlue,
            unfocusedBorderColor = BgBorder,
        ),
    )
}
