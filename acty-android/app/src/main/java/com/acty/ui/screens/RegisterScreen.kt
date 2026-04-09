package com.acty.ui.screens

import androidx.compose.foundation.background
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
import com.acty.data.VehicleEntry
import com.acty.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.UUID

@Composable
fun RegisterScreen(
    onRegisterSuccess:  () -> Unit,
    onNavigateToLogin:  () -> Unit,
) {
    val context      = LocalContext.current
    val auth         = remember { AuthManager(context) }
    val scope        = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    var username     by remember { mutableStateOf("") }
    var email        by remember { mutableStateOf("") }
    var password     by remember { mutableStateOf("") }
    var confirmPw    by remember { mutableStateOf("") }
    var pwVisible    by remember { mutableStateOf(false) }
    var cfVisible    by remember { mutableStateOf(false) }

    // Optional first vehicle
    var vMake        by remember { mutableStateOf("") }
    var vModel       by remember { mutableStateOf("") }
    var vYear        by remember { mutableStateOf("") }
    var vDrivetrain  by remember { mutableStateOf("") }

    var loading      by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    val drivetrains = listOf("FWD", "RWD", "AWD", "4WD")

    fun validate(): String? {
        if (username.isBlank())              return "Username is required."
        if (username.trim().length < 2)      return "Username must be at least 2 characters."
        if (!email.contains('@'))            return "Enter a valid email address."
        if (password.length < 8)             return "Password must be at least 8 characters."
        if (password != confirmPw)           return "Passwords do not match."
        return null
    }

    fun doRegister() {
        val err = validate()
        if (err != null) { errorMessage = err; return }
        focusManager.clearFocus()
        scope.launch {
            loading = true; errorMessage = ""
            delay(300L)
            val vehicles = buildList {
                if (vMake.isNotBlank() && vModel.isNotBlank()) {
                    add(VehicleEntry(
                        id         = UUID.randomUUID().toString(),
                        make       = vMake.trim(),
                        model      = vModel.trim(),
                        year       = vYear.trim().toIntOrNull() ?: 2020,
                        drivetrain = vDrivetrain,
                        isActive   = true,
                    ))
                }
            }
            when (val r = auth.register(
                username = username.trim(),
                email    = email.trim(),
                password = password,
                vehicles = vehicles,
            )) {
                is AuthResult.Success -> onRegisterSuccess()
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
            Spacer(Modifier.height(64.dp))

            // ── Brand ──────────────────────────────────────────
            Text("🌵", fontSize = 52.sp, textAlign = TextAlign.Center)
            Spacer(Modifier.height(10.dp))
            Text(
                "Create Account",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.ExtraBold,
                    color      = CactusBlue,
                ),
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Free forever. No credit card.",
                style = MaterialTheme.typography.bodyMedium.copy(color = TextDim),
            )
            Spacer(Modifier.height(32.dp))

            // ── Account fields ─────────────────────────────────
            Surface(
                shape           = RoundedCornerShape(20.dp),
                color           = Color.White,
                shadowElevation = 4.dp,
                modifier        = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    Text(
                        "Account Details",
                        style = MaterialTheme.typography.titleMedium.copy(
                            fontWeight = FontWeight.Bold, color = TextPrimary,
                        ),
                    )
                    Spacer(Modifier.height(16.dp))

                    if (errorMessage.isNotEmpty()) {
                        Surface(
                            shape    = RoundedCornerShape(10.dp),
                            color    = StatusRedBg,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                errorMessage,
                                style    = MaterialTheme.typography.bodySmall.copy(color = StatusRed),
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                            )
                        }
                        Spacer(Modifier.height(14.dp))
                    }

                    AuthField(
                        value         = username,
                        onValueChange = { username = it; errorMessage = "" },
                        label         = "Username",
                        imeAction     = ImeAction.Next,
                        onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                    )
                    Spacer(Modifier.height(12.dp))
                    AuthField(
                        value         = email,
                        onValueChange = { email = it; errorMessage = "" },
                        label         = "Email",
                        keyboardType  = KeyboardType.Email,
                        imeAction     = ImeAction.Next,
                        onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                    )
                    Spacer(Modifier.height(12.dp))
                    AuthField(
                        value                = password,
                        onValueChange        = { password = it; errorMessage = "" },
                        label                = "Password (min. 8 characters)",
                        keyboardType         = KeyboardType.Password,
                        imeAction            = ImeAction.Next,
                        onNext               = { focusManager.moveFocus(FocusDirection.Down) },
                        visualTransformation = if (pwVisible) VisualTransformation.None
                                               else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { pwVisible = !pwVisible }) {
                                Icon(
                                    if (pwVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                                    contentDescription = "Toggle",
                                    tint = TextDim,
                                )
                            }
                        },
                    )
                    Spacer(Modifier.height(12.dp))
                    AuthField(
                        value                = confirmPw,
                        onValueChange        = { confirmPw = it; errorMessage = "" },
                        label                = "Confirm Password",
                        keyboardType         = KeyboardType.Password,
                        imeAction            = ImeAction.Done,
                        onDone               = { doRegister() },
                        visualTransformation = if (cfVisible) VisualTransformation.None
                                               else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { cfVisible = !cfVisible }) {
                                Icon(
                                    if (cfVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                                    contentDescription = "Toggle",
                                    tint = TextDim,
                                )
                            }
                        },
                    )
                }
            }

            Spacer(Modifier.height(16.dp))

            // ── Optional first vehicle ─────────────────────────
            Surface(
                shape           = RoundedCornerShape(20.dp),
                color           = Color.White,
                shadowElevation = 4.dp,
                modifier        = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    Text(
                        "Your Vehicle",
                        style = MaterialTheme.typography.titleMedium.copy(
                            fontWeight = FontWeight.Bold, color = TextPrimary,
                        ),
                    )
                    Text(
                        "Optional — you can add vehicles later.",
                        style    = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                        modifier = Modifier.padding(top = 2.dp, bottom = 14.dp),
                    )

                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        AuthField(
                            value         = vYear,
                            onValueChange = { vYear = it },
                            label         = "Year",
                            keyboardType  = KeyboardType.Number,
                            imeAction     = ImeAction.Next,
                            onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                            modifier      = Modifier.weight(0.9f),
                        )
                        AuthField(
                            value         = vMake,
                            onValueChange = { vMake = it },
                            label         = "Make",
                            imeAction     = ImeAction.Next,
                            onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                            modifier      = Modifier.weight(1.1f),
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    AuthField(
                        value         = vModel,
                        onValueChange = { vModel = it },
                        label         = "Model",
                        imeAction     = ImeAction.Next,
                        onNext        = { focusManager.moveFocus(FocusDirection.Down) },
                    )
                    Spacer(Modifier.height(14.dp))

                    // Drivetrain chips
                    Text(
                        "Drivetrain",
                        style = MaterialTheme.typography.labelMedium.copy(color = TextSecondary),
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        drivetrains.forEach { dt ->
                            val selected = vDrivetrain == dt
                            FilterChip(
                                selected = selected,
                                onClick  = { vDrivetrain = if (selected) "" else dt },
                                label    = { Text(dt, fontWeight = FontWeight.SemiBold, fontSize = 13.sp) },
                                colors   = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = CactusBlue,
                                    selectedLabelColor     = Color.White,
                                ),
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

            // ── Submit ─────────────────────────────────────────
            Button(
                onClick  = { doRegister() },
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
                    Text("Create Account", fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                }
            }

            Spacer(Modifier.height(16.dp))
            Row(
                horizontalArrangement = Arrangement.Center,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Text(
                    "Already have an account?",
                    style = MaterialTheme.typography.bodyMedium.copy(color = TextDim),
                )
                TextButton(onClick = onNavigateToLogin) {
                    Text("Sign in", color = CactusBlue, fontWeight = FontWeight.SemiBold)
                }
            }
            Spacer(Modifier.height(48.dp))
        }
    }
}

// ── Overloaded AuthField with explicit modifier ───────────────────────────────

@Composable
fun AuthField(
    value:                String,
    onValueChange:        (String) -> Unit,
    label:                String,
    modifier:             Modifier                = Modifier.fillMaxWidth(),
    keyboardType:         KeyboardType            = KeyboardType.Text,
    imeAction:            ImeAction               = ImeAction.Next,
    onNext:               () -> Unit              = {},
    onDone:               () -> Unit              = {},
    visualTransformation: VisualTransformation    = VisualTransformation.None,
    trailingIcon:         @Composable (() -> Unit)? = null,
) {
    OutlinedTextField(
        value                = value,
        onValueChange        = onValueChange,
        label                = { Text(label) },
        singleLine           = true,
        modifier             = modifier,
        shape                = RoundedCornerShape(12.dp),
        keyboardOptions      = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
        keyboardActions      = KeyboardActions(onNext = { onNext() }, onDone = { onDone() }),
        visualTransformation = visualTransformation,
        trailingIcon         = trailingIcon,
        colors               = OutlinedTextFieldDefaults.colors(
            focusedBorderColor   = CactusBlue,
            focusedLabelColor    = CactusBlue,
            unfocusedBorderColor = BgBorder,
        ),
    )
}
