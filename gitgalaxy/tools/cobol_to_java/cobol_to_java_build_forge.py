#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Java Spring Build System Generator
#
# PURPOSE:
# Auto-generates the Maven pom.xml and application.yml configuration to ensure
# the translated Spring Boot architecture is immediately and perfectly compilable.
#
# ARCHITECTURAL DECISION:
# Generative AI frequently hallucinates incompatible library versions, mixes Maven
# and Gradle paradigms randomly, or omits critical runtime drivers (like PostgreSQL).
# By utilizing this static generation module to lay down the build infrastructure
# and properties, we establish a rigid, compilable sandbox. The autonomous agents
# are then restricted entirely to editing the business logic within the bounds
# of this pre-verified dependency graph.
# ==============================================================================


from typing import Optional

from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


def _dependency(group: str, artifact: str, scope: Optional[str] = None, optional: bool = False) -> str:
    lines = [
        "        <dependency>",
        f"            <groupId>{group}</groupId>",
        f"            <artifactId>{artifact}</artifactId>",
    ]
    if scope:
        lines.append(f"            <scope>{scope}</scope>")
    if optional:
        lines.append("            <optional>true</optional>")
    lines.append("        </dependency>")
    return "\n".join(lines) + "\n"


def generate_pom_xml(group_id: str, artifact_id: str, target: Optional[JavaTarget] = None) -> str:
    """Scaffolds a production-ready Maven pom.xml for the microservice.

    `target` (#3613) picks the Java and Spring Boot versions, the JDBC driver, and
    whether Lombok and Spring Batch are on the classpath; the default target writes
    the historic pom byte for byte."""
    t = target or JavaTarget()
    drv_group, drv_artifact = t.driver()[:2]
    deps = [
        _dependency("org.springframework.boot", "spring-boot-starter-web"),
        _dependency("org.springframework.boot", "spring-boot-starter-data-jpa"),
    ]
    if t.features.batch:
        deps.append(_dependency("org.springframework.boot", "spring-boot-starter-batch"))
    deps.append(_dependency(drv_group, drv_artifact, scope="runtime"))
    if t.lombok:
        deps.append(_dependency("org.projectlombok", "lombok", optional=True))
    deps.append(_dependency("org.slf4j", "slf4j-api"))
    deps.append(_dependency("org.springframework.boot", "spring-boot-starter-test", scope="test"))
    if t.database.engine != "h2":
        deps.append(_dependency("com.h2database", "h2", scope="test"))
    plugin_config = (
        """
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>"""
        if t.lombok
        else ""
    )
    pom = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{t.spring_boot.version}</version>
        <relativePath/> </parent>

    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>{t.project.version}</version>
    <name>{artifact_id}</name>
    <description>{t.project.description}</description>

    <properties>
        <java.version>{t.java.version}</java.version>
    </properties>

    <dependencies>
{chr(10).join(deps)}    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>{plugin_config}
            </plugin>
        </plugins>
    </build>
</project>
"""
    return pom


# The io.spring.dependency-management plugin release paired with each Spring Boot minor.
_DEPENDENCY_MANAGEMENT = {"3.0": "1.1.0", "3.1": "1.1.3", "3.2": "1.1.4", "3.3": "1.1.6", "3.4": "1.1.7"}


def generate_build_gradle(group_id: str, target: JavaTarget) -> str:
    """The Gradle (Groovy DSL) build equivalent of generate_pom_xml (#3613); the project
    name (artifactId) goes in settings.gradle."""
    t = target
    minor = ".".join(t.spring_boot.version.split(".")[:2])
    dm = _DEPENDENCY_MANAGEMENT.get(minor, "1.1.7")
    drv_group, drv_artifact = t.driver()[:2]
    deps = [
        "    implementation 'org.springframework.boot:spring-boot-starter-web'",
        "    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'",
    ]
    if t.features.batch:
        deps.append("    implementation 'org.springframework.boot:spring-boot-starter-batch'")
    deps.append(f"    runtimeOnly '{drv_group}:{drv_artifact}'")
    if t.lombok:
        deps += ["    compileOnly 'org.projectlombok:lombok'", "    annotationProcessor 'org.projectlombok:lombok'"]
    deps.append("    implementation 'org.slf4j:slf4j-api'")
    deps.append("    testImplementation 'org.springframework.boot:spring-boot-starter-test'")
    if t.database.engine != "h2":
        deps.append("    testRuntimeOnly 'com.h2database:h2'")
    return f"""plugins {{
    id 'java'
    id 'org.springframework.boot' version '{t.spring_boot.version}'
    id 'io.spring.dependency-management' version '{dm}'
}}

group = '{group_id}'
version = '{t.project.version}'
description = '{t.project.description}'

java {{
    toolchain {{
        languageVersion = JavaLanguageVersion.of({t.java.version})
    }}
}}

repositories {{
    mavenCentral()
}}

dependencies {{
{chr(10).join(deps)}
}}

tasks.named('test') {{
    useJUnitPlatform()
}}
"""


def generate_settings_gradle(artifact_id: str) -> str:
    return f"rootProject.name = '{artifact_id}'\n"


def generate_application_yml(artifact_id: str, target: Optional[JavaTarget] = None) -> str:
    """Scaffolds the application.yml: datasource, JPA and (when enabled) Spring Batch,
    for the target's database (#3613); the default target writes the historic file."""
    t = target or JavaTarget()
    _, _, driver_class, dialect, url = t.driver()
    db_name = artifact_id.replace("-", "_")
    batch = (
        """
  batch:
    jdbc:
      initialize-schema: always
    job:
      enabled: false # Prevents batch jobs from auto-running on startup
"""
        if t.features.batch
        else ""
    )
    ddl_note = " # Automatically creates tables from Entities" if t.database.ddl_auto == "update" else ""
    yml = f"""server:
  port: 8080

spring:
  application:
    name: {artifact_id}

  datasource:
    # TODO: Update these credentials for your target environment
    url: {url.format(db=db_name)}
    username: {t.database.username}
    password: password
    driver-class-name: {driver_class}

  jpa:
    hibernate:
      ddl-auto: {t.database.ddl_auto}{ddl_note}
    show-sql: {str(t.database.show_sql).lower()}
    properties:
      hibernate:
        format_sql: true
        dialect: {dialect}
{batch}"""
    return yml


def generate_main_class(package_name: str, class_name: str) -> str:
    """Scaffolds the Spring Boot Application entry point."""
    java = f"""package {package_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {class_name}Application {{

    public static void main(String[] args) {{
        SpringApplication.run({class_name}Application.class, args);
    }}
}}
"""
    return java
